"""
Hybrid DeepAgent-based Workflow Manager with Parallel Execution

This module combines the best of DeepAgents and Standard workflows:
- DeepAgents: SubAgentMiddleware, FilesystemMiddleware for advanced capabilities
- Standard: Parallel execution, SharedContext, Dynamic workflows, H100 optimization

Key Features:
- ✅ Parallel coding execution (up to 25 concurrent agents on H100)
- ✅ Thread-safe SharedContext for agent communication
- ✅ Dynamic workflow selection based on task type
- ✅ Adaptive parallelism calculation
- ✅ Task grouping for efficient execution
- ✅ Review loops with conditional logic
- ✅ DeepAgents middleware integration
"""
import asyncio
import glob
import json
import os
import logging
import re
from typing import Dict, Any, List, Optional, AsyncGenerator, Literal
from datetime import datetime
from dataclasses import dataclass, field

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# Initialize logger
logger = logging.getLogger(__name__)

# DeepAgents imports
try:
    from deepagents import create_deep_agent
    from deepagents.middleware.subagents import SubAgentMiddleware
    from deepagents.middleware.filesystem import FilesystemMiddleware
    from deepagents.backends.filesystem import FilesystemBackend
    DEEPAGENTS_AVAILABLE = True
    logger.info("DeepAgents v0.3.0 available - hybrid mode enabled")
except ImportError:
    DEEPAGENTS_AVAILABLE = False
    create_deep_agent = None
    SubAgentMiddleware = None
    FilesystemMiddleware = None
    FilesystemBackend = None
    logger.warning("DeepAgents not available - falling back to standard mode")

from app.core.config import settings
from app.agent.base.interface import BaseWorkflow
from app.agent.langchain.shared_context import SharedContext, ContextEntry


# ==================== Global Middleware Singleton ====================
# ROOT CAUSE: DeepAgents uses a global registry for middleware.
# Creating multiple agents with new middleware instances causes:
# "Please remove duplicate middleware instance" error
#
# SOLUTION: Share singleton middleware instances across all agents
# in the same process to prevent duplication in global registry.

_global_middleware_cache = {}
_middleware_lock = asyncio.Lock()


# ==================== Dynamic Workflow Templates ====================

TaskType = Literal[
    "code_generation",
    "bug_fix",
    "refactoring",
    "test_generation",
    "code_review",
    "documentation",
    "general"
]

WORKFLOW_TEMPLATES: Dict[TaskType, Dict[str, Any]] = {
    "code_generation": {
        "name": "Code Generation Workflow",
        "phases": ["Analysis", "Planning", "Parallel Coding", "Review", "Fix (if needed)"],
        "supports_parallel": True,
        "has_review_loop": True
    },
    "bug_fix": {
        "name": "Bug Fix Workflow",
        "phases": ["Analysis", "Debug", "Fix", "Test"],
        "supports_parallel": False,  # Bug fixes are usually focused
        "has_review_loop": True
    },
    "refactoring": {
        "name": "Refactoring Workflow",
        "phases": ["Analysis", "Plan Refactoring", "Parallel Refactor", "Review"],
        "supports_parallel": True,
        "has_review_loop": True
    },
    "test_generation": {
        "name": "Test Generation Workflow",
        "phases": ["Analysis", "Parallel Test Creation", "Validation"],
        "supports_parallel": True,
        "has_review_loop": False
    },
    "code_review": {
        "name": "Code Review Workflow",
        "phases": ["Analysis", "Parallel Review", "Summary"],
        "supports_parallel": True,
        "has_review_loop": False
    },
    "general": {
        "name": "General Chat Workflow",
        "phases": ["Response"],
        "supports_parallel": False,
        "has_review_loop": False
    }
}


# ==================== Main Workflow Manager ====================

class DeepAgentWorkflowManager(BaseWorkflow):
    """
    Hybrid workflow manager combining DeepAgents middleware with parallel execution.

    Features:
    - DeepAgents SubAgentMiddleware and FilesystemMiddleware
    - Parallel agent execution using asyncio.gather
    - SharedContext for agent communication
    - Dynamic workflow selection
    - H100 GPU optimization (up to 25 concurrent agents)
    """

    def __init__(
        self,
        agent_id: str = "hybrid_deepagent",
        model_name: str = "gpt-4o",
        temperature: float = 0.7,
        enable_subagents: bool = True,
        enable_filesystem: bool = True,
        enable_parallel: bool = True,
        max_parallel_agents: int = 25,
        workspace: str = "/home/user/workspace"
    ):
        """
        Initialize Hybrid DeepAgent workflow manager.

        Args:
            agent_id: Unique identifier for this agent
            model_name: Model to use (vLLM endpoint)
            temperature: Model temperature
            enable_subagents: Enable SubAgentMiddleware
            enable_filesystem: Enable FilesystemMiddleware
            enable_parallel: Enable parallel execution
            max_parallel_agents: Max concurrent agents (H100 optimized: 25)
            workspace: Base workspace directory
        """
        if not DEEPAGENTS_AVAILABLE:
            raise ImportError(
                "DeepAgents is not installed. "
                "Install with: pip install deepagents tavily-python"
            )

        self.agent_id = agent_id
        self.model_name = model_name
        self.temperature = temperature
        self.workspace = workspace
        self.enable_parallel = enable_parallel
        self.max_parallel_agents = max_parallel_agents
        self.adaptive_parallelism = True  # Adjust based on task count

        # Initialize LLM - using vLLM endpoints
        self.llm = ChatOpenAI(
            base_url=settings.vllm_reasoning_endpoint,
            model=settings.reasoning_model,
            temperature=temperature,
            api_key="EMPTY",
            streaming=True
        )

        # Build middleware stack using SINGLETON pattern
        # This prevents "duplicate middleware instance" errors from DeepAgents
        self.middleware_stack = []

        if enable_filesystem:
            try:
                # Use global singleton FilesystemMiddleware
                if "filesystem" not in _global_middleware_cache:
                    # Create shared workspace for all agents
                    fs_path = os.path.join(workspace, '.deepagents', 'shared')
                    os.makedirs(fs_path, exist_ok=True)
                    fs_backend = FilesystemBackend(root_dir=fs_path)
                    _global_middleware_cache["filesystem"] = FilesystemMiddleware(backend=fs_backend)
                    logger.info(f"✅ Created SINGLETON FilesystemMiddleware: {fs_path}")
                else:
                    logger.info("♻️  Reusing existing FilesystemMiddleware singleton")

                self.middleware_stack.append(_global_middleware_cache["filesystem"])
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize FilesystemMiddleware: {e}")

        if enable_subagents:
            try:
                # Use global singleton SubAgentMiddleware
                if "subagent" not in _global_middleware_cache:
                    _global_middleware_cache["subagent"] = SubAgentMiddleware(
                        default_model=self.llm,
                        default_tools=[]
                    )
                    logger.info("✅ Created SINGLETON SubAgentMiddleware")
                else:
                    logger.info("♻️  Reusing existing SubAgentMiddleware singleton")

                self.middleware_stack.append(_global_middleware_cache["subagent"])
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize SubAgentMiddleware: {e}")

        # Create DeepAgent
        try:
            # Log middleware stack for debugging
            middleware_types = [type(m).__name__ for m in self.middleware_stack]
            logger.info(f"Creating DeepAgent '{agent_id}' with middleware: {middleware_types}")

            # Check for duplicate middleware types
            if len(middleware_types) != len(set(middleware_types)):
                logger.error(f"Duplicate middleware detected in stack: {middleware_types}")
                raise ValueError(f"Duplicate middleware types in middleware_stack: {middleware_types}")

            self.agent = create_deep_agent(
                model=self.llm,
                tools=[],
                middleware=self.middleware_stack if self.middleware_stack else [],
                system_prompt="""You are an advanced AI coding assistant with parallel execution capabilities.

Your role is to collaborate with other agents to deliver high-quality code:
1. Analyze tasks and create detailed plans
2. Execute coding tasks in parallel when possible
3. Communicate via SharedContext with other agents
4. Review and improve code iteratively

Always prioritize code quality, collaboration, and efficiency."""
            )
            logger.info(f"✅ Hybrid DeepAgent created successfully: {agent_id}")
        except Exception as e:
            logger.error(f"❌ Failed to create DeepAgent '{agent_id}': {e}")
            raise

    async def execute(
        self,
        user_request: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Execute the coding workflow (non-streaming).

        Args:
            user_request: User's coding request
            context: Optional run context

        Returns:
            Final result from the workflow
        """
        final_result = ""
        artifacts = []

        try:
            async for update in self.execute_stream(user_request, context, session_id="default"):
                # Collect important information
                if update.get("type") == "artifact":
                    artifact = update.get("artifact", {})
                    artifacts.append(f"Created: {artifact.get('filename', 'unknown')}")
                elif update.get("type") == "response":
                    final_result = update.get("message", "")
                elif update.get("type") == "error":
                    final_result = f"Error: {update.get('message', 'Unknown error')}"
                    break

            # Build final result
            if artifacts:
                result_parts = ["Workflow completed successfully!", ""]
                result_parts.append("Generated files:")
                result_parts.extend(f"- {artifact}" for artifact in artifacts)
                if final_result:
                    result_parts.append("")
                    result_parts.append(final_result)
                return "\n".join(result_parts)
            elif final_result:
                return final_result
            else:
                return "Workflow completed successfully!"

        except Exception as e:
            logger.exception(f"Error in execute: {e}")
            return f"Error: {str(e)}"

    async def execute_stream(
        self,
        user_request: str,
        context: Optional[Dict[str, Any]] = None,
        session_id: str = "default"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute workflow with streaming updates.

        Args:
            user_request: User's request
            context: Optional context
            session_id: Session identifier

        Yields:
            Workflow updates
        """
        try:
            # Workspace exploration
            if self.workspace and os.path.exists(self.workspace):
                import glob
                code_patterns = ["*.py", "*.js", "*.ts", "*.tsx", "*.java", "*.cpp", "*.go", "*.rs"]
                existing_files = []

                for pattern in code_patterns:
                    existing_files.extend(
                        glob.glob(os.path.join(self.workspace, "**", pattern), recursive=True)
                    )

                if existing_files:
                    file_list = [os.path.basename(f) for f in existing_files[:10]]
                    more_count = len(existing_files) - 10

                    yield {
                        "agent": "WorkspaceExplorer",
                        "type": "workspace_info",
                        "status": "info",
                        "message": f"📁 Found {len(existing_files)} existing file(s)",
                        "workspace": self.workspace,
                        "file_count": len(existing_files),
                        "files": file_list + ([f"... and {more_count} more"] if more_count > 0 else []),
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    yield {
                        "agent": "WorkspaceExplorer",
                        "type": "workspace_info",
                        "status": "info",
                        "message": "📂 Workspace is empty - starting fresh project",
                        "workspace": self.workspace,
                        "file_count": 0,
                        "timestamp": datetime.now().isoformat()
                    }

            # Phase 1: Supervisor Analysis
            yield {
                "agent": "SupervisorAgent",
                "type": "thinking",
                "status": "running",
                "message": "🧠 Analyzing request and selecting workflow...",
                "timestamp": datetime.now().isoformat()
            }

            analysis_result, task_type = await self._analyze_task(user_request)

            yield {
                "agent": "SupervisorAgent",
                "type": "analysis",
                "status": "completed",
                "message": f"✅ Task classified as: {task_type}",
                "analysis": analysis_result,
                "task_type": task_type,
                "workflow": WORKFLOW_TEMPLATES[task_type]["name"],
                "timestamp": datetime.now().isoformat()
            }

            # Phase 2: Execute based on task type
            if task_type in ["code_generation", "refactoring", "test_generation"]:
                async for update in self._execute_parallel_coding_workflow(
                    user_request, analysis_result, task_type, session_id
                ):
                    yield update
            elif task_type == "bug_fix":
                async for update in self._execute_bugfix_workflow(
                    user_request, analysis_result, session_id
                ):
                    yield update
            elif task_type == "code_review":
                async for update in self._execute_review_workflow(
                    user_request, analysis_result, session_id
                ):
                    yield update
            else:
                # General chat mode
                async for update in self._execute_chat_mode(user_request, session_id):
                    yield update

            # Final completion
            yield {
                "agent": "HybridDeepAgent",
                "type": "completion",
                "status": "completed",
                "message": "✅ Workflow completed successfully",
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.exception(f"Error in workflow execution: {e}")
            yield {
                "agent": "HybridDeepAgent",
                "type": "error",
                "status": "error",
                "message": f"❌ Error: {str(e)}",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def _analyze_task(self, user_request: str) -> tuple[str, TaskType]:
        """Analyze task and determine type."""
        supervisor_prompt = self._build_supervisor_prompt()

        analysis_result = ""
        # Use direct LLM instead of self.agent to avoid LangGraph state issues
        async for chunk in self.llm.astream([
            SystemMessage(content=supervisor_prompt),
            HumanMessage(content=user_request)
        ]):
            if chunk.content:
                analysis_result += chunk.content

        task_type = self._parse_task_type(analysis_result)
        return analysis_result, task_type

    async def _execute_parallel_coding_workflow(
        self,
        user_request: str,
        analysis: str,
        task_type: TaskType,
        session_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute coding workflow with parallel agent execution.

        This is the core hybrid implementation combining:
        - DeepAgents SubAgentMiddleware for context isolation
        - Parallel execution with asyncio.gather
        - SharedContext for agent communication
        """
        # Create shared context for parallel agents
        shared_context = SharedContext()

        # Phase 1: Planning
        yield {
            "agent": "PlanningAgent",
            "type": "thinking",
            "status": "running",
            "message": "📋 Creating implementation plan...",
            "timestamp": datetime.now().isoformat()
        }

        plan_text, tasks = await self._create_plan(user_request, analysis)

        yield {
            "agent": "PlanningAgent",
            "type": "plan",
            "status": "completed",
            "message": f"✅ Plan created with {len(tasks)} tasks",
            "plan": plan_text,
            "tasks": tasks,
            "timestamp": datetime.now().isoformat()
        }

        # Phase 2: Parallel Implementation
        use_parallel = self.enable_parallel and len(tasks) >= 2

        if use_parallel:
            # Calculate optimal parallelism
            optimal_parallel = self.calculate_optimal_parallel(len(tasks))

            yield {
                "agent": "CodingCoordinator",
                "type": "parallel_start",
                "status": "running",
                "message": f"🚀 Starting parallel execution with up to {optimal_parallel} concurrent agents",
                "execution_mode": "parallel",
                "parallel_config": {
                    "max_parallel": optimal_parallel,
                    "total_tasks": len(tasks)
                },
                "timestamp": datetime.now().isoformat()
            }

            # Execute in parallel
            async for update in self._execute_parallel_coding(
                tasks, user_request, plan_text, shared_context, optimal_parallel
            ):
                yield update
        else:
            # Sequential execution for single task or disabled parallel
            yield {
                "agent": "CodingAgent",
                "type": "thinking",
                "status": "running",
                "message": f"🔨 Implementing {len(tasks)} task(s) sequentially...",
                "timestamp": datetime.now().isoformat()
            }

            async for update in self._execute_sequential_coding(
                tasks, user_request, plan_text
            ):
                yield update

        # Phase 3: Review (conditional)
        if WORKFLOW_TEMPLATES[task_type]["has_review_loop"]:
            async for update in self._execute_review_phase(
                shared_context, user_request
            ):
                yield update

        # Phase 4: Shared Context Summary
        yield {
            "agent": "ContextManager",
            "type": "shared_context",
            "status": "completed",
            "message": "📊 Shared context summary",
            "shared_context": {
                "entries": shared_context.get_entries_summary(),
                "access_log": shared_context.get_access_log()
            },
            "timestamp": datetime.now().isoformat()
        }

        # Phase 5: Source Tree Display
        source_tree_info = self._generate_source_tree(self.workspace)
        yield {
            "agent": "FileSystemAgent",
            "type": "source_tree",
            "status": "completed",
            "message": f"📂 Generated {source_tree_info['file_count']} files",
            "source_tree": source_tree_info['tree'],
            "files": source_tree_info['files'],
            "workspace": source_tree_info['workspace'],
            "timestamp": datetime.now().isoformat()
        }

    async def _execute_parallel_coding(
        self,
        tasks: List[Dict],
        user_request: str,
        plan_text: str,
        shared_context: SharedContext,
        optimal_parallel: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute multiple coding tasks in parallel with real-time progress updates.

        Uses asyncio.Queue to stream progress from parallel agents.
        """
        all_artifacts = []
        progress_queue = asyncio.Queue()

        # Process tasks in batches
        batch_count = (len(tasks) + optimal_parallel - 1) // optimal_parallel

        for batch_start in range(0, len(tasks), optimal_parallel):
            batch_end = min(batch_start + optimal_parallel, len(tasks))
            batch_tasks = tasks[batch_start:batch_end]
            current_batch = batch_start // optimal_parallel + 1

            yield {
                "agent": "CodingCoordinator",
                "type": "batch_start",
                "status": "running",
                "message": f"📦 Batch {current_batch}/{batch_count}: Processing {len(batch_tasks)} tasks in parallel",
                "batch_info": {
                    "batch_num": current_batch,
                    "total_batches": batch_count,
                    "tasks_in_batch": len(batch_tasks)
                },
                "timestamp": datetime.now().isoformat()
            }

            # Create parallel tasks with progress queue
            pending_tasks = []
            for idx, task in enumerate(batch_tasks):
                agent_id = f"CodingAgent_{batch_start + idx + 1}"
                pending_tasks.append(
                    asyncio.create_task(
                        self._execute_single_coding_task(
                            task, user_request, plan_text, shared_context,
                            agent_id, batch_start + idx + 1, len(tasks),
                            progress_queue=progress_queue
                        )
                    )
                )

            # Monitor progress while tasks are running
            completed_count = 0
            results = []

            while completed_count < len(batch_tasks):
                # Check for progress updates or task completion
                try:
                    # Wait for progress update with timeout
                    update = await asyncio.wait_for(progress_queue.get(), timeout=0.1)

                    # Yield progress update to frontend
                    yield update

                    # Track completions
                    if update.get("type") == "task_complete":
                        completed_count += 1
                        results.append(update.get("result"))

                except asyncio.TimeoutError:
                    # No update yet, check if any task completed
                    done, pending = await asyncio.wait(
                        pending_tasks,
                        timeout=0,
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    # If no tasks done and no queue updates, continue waiting
                    if not done:
                        continue

                    # Update pending tasks list
                    pending_tasks = list(pending)

            # Wait for any remaining tasks
            if pending_tasks:
                final_results = await asyncio.gather(*pending_tasks, return_exceptions=True)

                # Handle any errors
                for idx, result in enumerate(final_results):
                    if isinstance(result, Exception):
                        logger.error(f"Task failed: {result}")
                        yield {
                            "agent": f"CodingAgent_{batch_start + idx + 1}",
                            "type": "error",
                            "status": "error",
                            "message": f"❌ Task failed: {str(result)}",
                            "timestamp": datetime.now().isoformat()
                        }
                    elif result not in results:
                        results.append(result)

            # Collect artifacts
            for result in results:
                if result and not isinstance(result, Exception):
                    all_artifacts.append(result)
                    yield {
                        "agent": result.get("agent_id", "CodingAgent"),
                        "type": "artifact",
                        "status": "completed",
                        "message": f"✅ Completed {result['filename']}",
                        "artifact": result,
                        "timestamp": datetime.now().isoformat()
                    }

        yield {
            "agent": "CodingCoordinator",
            "type": "parallel_complete",
            "status": "completed",
            "message": f"🎉 Parallel execution completed: {len(all_artifacts)} files created",
            "parallel_summary": {
                "total_tasks": len(tasks),
                "successful": len(all_artifacts),
                "max_concurrent": optimal_parallel
            },
            "timestamp": datetime.now().isoformat()
        }

    async def _execute_single_coding_task(
        self,
        task: Dict,
        user_request: str,
        plan_text: str,
        shared_context: SharedContext,
        agent_id: str,
        task_num: int,
        total_tasks: int,
        progress_queue: Optional[asyncio.Queue] = None
    ) -> Dict[str, Any]:
        """Execute a single coding task with SharedContext access and progress reporting."""

        # Report task start
        if progress_queue:
            await progress_queue.put({
                "agent": agent_id,
                "type": "task_start",
                "status": "running",
                "message": f"🚀 Starting: {task.get('description')}",
                "task_num": task_num,
                "timestamp": datetime.now().isoformat()
            })

        # Build prompt with parallel execution context
        coding_prompt = self._build_parallel_coding_prompt(
            task, user_request, plan_text, agent_id, task_num, total_tasks
        )

        # Execute with streaming progress
        code_output = ""
        line_count = 0

        async for chunk_text, full_text in self._stream_llm_response(
            [
                SystemMessage(content=coding_prompt),
                HumanMessage(content=f"Implement: {task.get('description')}")
            ],
            chunk_size=6,
            filter_tags=True
        ):
            if chunk_text and progress_queue:  # Intermediate chunk
                line_count += chunk_text.count('\n')
                await progress_queue.put({
                    "agent": agent_id,
                    "type": "code_chunk",
                    "status": "streaming",
                    "message": f"💻 {agent_id} writing... ({line_count} lines)",
                    "chunk": chunk_text,
                    "task_num": task_num,
                    "timestamp": datetime.now().isoformat()
                })
            elif not chunk_text:  # Final chunk
                code_output = full_text

        filename = task.get('filename', f'task_{task_num}.py')

        # Store in shared context
        await shared_context.set(
            agent_id=agent_id,
            agent_type="CodingAgent",
            key="output",
            value=code_output,
            description=f"Code for {filename}"
        )

        result = {
            "task_num": task_num,
            "agent_id": agent_id,
            "description": task.get('description'),
            "filename": filename,
            "language": task.get('language', 'python'),
            "content": code_output
        }

        # Report completion
        if progress_queue:
            await progress_queue.put({
                "agent": agent_id,
                "type": "task_complete",
                "status": "completed",
                "message": f"✅ Completed: {filename}",
                "task_num": task_num,
                "result": result,
                "timestamp": datetime.now().isoformat()
            })

        return result

    async def _execute_sequential_coding(
        self,
        tasks: List[Dict],
        user_request: str,
        plan_text: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute tasks sequentially (fallback or single task)."""

        for idx, task in enumerate(tasks):
            task_num = idx + 1

            yield {
                "agent": "CodingAgent",
                "type": "task_start",
                "status": "running",
                "message": f"📝 Task {task_num}/{len(tasks)}: {task.get('description')}",
                "timestamp": datetime.now().isoformat()
            }

            coding_prompt = self._build_coding_prompt(task, user_request, plan_text)

            # Stream code generation with 6-line chunks
            code_output = ""
            line_count = 0

            async for chunk_text, full_text in self._stream_llm_response(
                [
                    SystemMessage(content=coding_prompt),
                    HumanMessage(content=f"Implement: {task.get('description')}")
                ],
                chunk_size=6,
                filter_tags=True
            ):
                if chunk_text:  # Intermediate chunk
                    line_count += chunk_text.count('\n')
                    yield {
                        "agent": "CodingAgent",
                        "type": "code_chunk",
                        "status": "streaming",
                        "message": f"💻 Writing code... ({line_count} lines)",
                        "chunk": chunk_text,
                        "task_num": task_num,
                        "timestamp": datetime.now().isoformat()
                    }
                else:  # Final chunk
                    code_output = full_text

            filename = task.get('filename', f'task_{task_num}.py')

            yield {
                "agent": "CodingAgent",
                "type": "artifact",
                "status": "completed",
                "message": f"✅ Completed {filename}",
                "artifact": {
                    "filename": filename,
                    "language": task.get('language', 'python'),
                    "content": code_output,
                    "task_num": task_num
                },
                "timestamp": datetime.now().isoformat()
            }

    async def _execute_review_phase(
        self,
        shared_context: SharedContext,
        user_request: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute review phase with shared context."""

        yield {
            "agent": "ReviewAgent",
            "type": "thinking",
            "status": "running",
            "message": "🔍 Reviewing implementation...",
            "timestamp": datetime.now().isoformat()
        }

        # Get all outputs from shared context
        review_prompt = self._build_review_prompt(shared_context, user_request)

        # Stream review with 6-line chunks
        review_text = ""
        line_count = 0

        async for chunk_text, full_text in self._stream_llm_response(
            [
                SystemMessage(content=review_prompt),
                HumanMessage(content="Review the implementation")
            ],
            chunk_size=6,
            filter_tags=True
        ):
            if chunk_text:  # Intermediate chunk
                line_count += chunk_text.count('\n')
                yield {
                    "agent": "ReviewAgent",
                    "type": "review_chunk",
                    "status": "streaming",
                    "message": f"📝 Writing review... ({line_count} lines)",
                    "chunk": chunk_text,
                    "timestamp": datetime.now().isoformat()
                }
            else:  # Final chunk
                review_text = full_text

        yield {
            "agent": "ReviewAgent",
            "type": "review",
            "status": "completed",
            "message": "✅ Review completed",
            "review": review_text,
            "timestamp": datetime.now().isoformat()
        }

    async def _execute_bugfix_workflow(
        self,
        user_request: str,
        analysis: str,
        session_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute bug fix workflow (sequential)."""
        yield {
            "agent": "DebugAgent",
            "type": "thinking",
            "status": "running",
            "message": "🐛 Analyzing bug and creating fix...",
            "timestamp": datetime.now().isoformat()
        }

        # Simple chat mode for bug fixes
        async for update in self._execute_chat_mode(user_request, session_id):
            yield update

    async def _execute_review_workflow(
        self,
        user_request: str,
        analysis: str,
        session_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute code review workflow."""
        yield {
            "agent": "ReviewAgent",
            "type": "thinking",
            "status": "running",
            "message": "🔍 Performing code review...",
            "timestamp": datetime.now().isoformat()
        }

        async for update in self._execute_chat_mode(user_request, session_id):
            yield update

    async def _execute_chat_mode(
        self,
        user_request: str,
        session_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute simple chat mode."""
        yield {
            "agent": "ChatAgent",
            "type": "thinking",
            "status": "running",
            "message": "💬 Processing your request...",
            "timestamp": datetime.now().isoformat()
        }

        response = ""
        async for chunk in self.llm.astream([
            HumanMessage(content=user_request)
        ]):
            if chunk.content:
                response += chunk.content

        yield {
            "agent": "ChatAgent",
            "type": "response",
            "status": "completed",
            "message": response,
            "timestamp": datetime.now().isoformat()
        }

    async def _create_plan(
        self,
        user_request: str,
        analysis: str
    ) -> tuple[str, List[Dict]]:
        """Create implementation plan."""
        planning_prompt = self._build_planning_prompt(user_request, analysis)

        plan_text = ""
        async for chunk in self.llm.astream([
            SystemMessage(content=planning_prompt),
            HumanMessage(content=user_request)
        ]):
            if chunk.content:
                plan_text += chunk.content

        tasks = self._parse_tasks_from_plan(plan_text)
        return plan_text, tasks

    # ==================== Helper Methods ====================

    def _filter_reasoning_tags(self, text: str) -> str:
        """
        Filter out reasoning tags like </think> from LLM output.

        DeepSeek-R1 and similar reasoning models output <think>...</think> tags.
        We want to remove these from the final output shown to users.
        """
        # Remove </think> closing tags
        text = text.replace('</think>', '')

        # Remove opening <think> tags and everything until closing tag
        import re
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)

        return text.strip()

    def _generate_source_tree(self, workspace: str) -> Dict[str, Any]:
        """
        Generate source tree structure from workspace.

        Returns:
            Dictionary with tree structure and file list
        """
        import glob

        if not workspace or not os.path.exists(workspace):
            return {"files": [], "tree": "No workspace"}

        # Collect all source files
        code_patterns = ["*.py", "*.js", "*.ts", "*.tsx", "*.java", "*.cpp", "*.go", "*.rs", "*.md", "*.txt", "*.json", "*.yaml", "*.yml"]
        all_files = []

        for pattern in code_patterns:
            files = glob.glob(os.path.join(workspace, "**", pattern), recursive=True)
            all_files.extend(files)

        # Sort files
        all_files.sort()

        # Create relative paths
        relative_files = [os.path.relpath(f, workspace) for f in all_files]

        # Build tree structure
        tree_lines = ["📁 " + os.path.basename(workspace) + "/"]

        # Group by directory
        dir_structure = {}
        for file_path in relative_files:
            parts = file_path.split(os.sep)
            if len(parts) == 1:
                # Root level file
                if "." not in dir_structure:
                    dir_structure["."] = []
                dir_structure["."].append(parts[0])
            else:
                # Nested file
                dir_name = parts[0]
                if dir_name not in dir_structure:
                    dir_structure[dir_name] = []
                dir_structure[dir_name].append(os.path.join(*parts[1:]))

        # Generate tree representation
        dirs = sorted([d for d in dir_structure.keys() if d != "."])
        root_files = sorted(dir_structure.get(".", []))

        # Add directories first
        for idx, dir_name in enumerate(dirs):
            is_last_dir = (idx == len(dirs) - 1) and len(root_files) == 0
            prefix = "└── " if is_last_dir else "├── "
            tree_lines.append(f"  {prefix}📁 {dir_name}/")

            # Add files in this directory
            dir_files = sorted(dir_structure[dir_name])
            for file_idx, file_name in enumerate(dir_files):
                is_last_file = file_idx == len(dir_files) - 1
                file_prefix = "    └── " if is_last_file else "    ├── "
                tree_lines.append(f"  {file_prefix}📄 {file_name}")

        # Add root level files
        for file_idx, file_name in enumerate(root_files):
            is_last = file_idx == len(root_files) - 1
            prefix = "└── " if is_last else "├── "
            tree_lines.append(f"  {prefix}📄 {file_name}")

        return {
            "files": relative_files,
            "tree": "\n".join(tree_lines),
            "file_count": len(relative_files),
            "workspace": workspace
        }

    async def _stream_llm_response(
        self,
        messages: list,
        chunk_size: int = 6,
        filter_tags: bool = True
    ) -> AsyncGenerator[tuple[str, str], None]:
        """
        Stream LLM response with chunk-based updates and tag filtering.

        Args:
            messages: Messages to send to LLM
            chunk_size: Number of lines per chunk (default: 6)
            filter_tags: Whether to filter </think> tags

        Yields:
            Tuple of (chunk_text, full_text_so_far)
        """
        full_response = ""
        line_buffer = []

        async for chunk in self.llm.astream(messages):
            if chunk.content:
                full_response += chunk.content

                # Split by newlines for line counting
                lines = chunk.content.split('\n')
                line_buffer.extend(lines)

                # Yield every chunk_size lines
                while len(line_buffer) >= chunk_size:
                    chunk_lines = line_buffer[:chunk_size]
                    line_buffer = line_buffer[chunk_size:]

                    chunk_text = '\n'.join(chunk_lines)
                    if filter_tags:
                        chunk_text = self._filter_reasoning_tags(chunk_text)

                    yield (chunk_text, full_response)

        # Yield remaining lines
        if line_buffer:
            chunk_text = '\n'.join(line_buffer)
            if filter_tags:
                chunk_text = self._filter_reasoning_tags(chunk_text)

            yield (chunk_text, full_response)

        # Final cleanup of full response
        if filter_tags:
            full_response = self._filter_reasoning_tags(full_response)

        yield ("", full_response)  # Final yield with complete text

    def calculate_optimal_parallel(self, task_count: int) -> int:
        """
        Calculate optimal parallelism for H100 GPU.

        H100 96GB with vLLM can handle 20-30 concurrent requests efficiently.
        """
        if not self.adaptive_parallelism:
            return self.max_parallel_agents

        if task_count <= 5:
            # Small projects: Run all in parallel
            return task_count
        elif task_count <= self.max_parallel_agents:
            # Medium: Use all available
            return self.max_parallel_agents
        else:
            # Large: Cap at H100 optimal
            return self.max_parallel_agents

    def _parse_task_type(self, analysis: str) -> TaskType:
        """Parse task type from analysis."""
        match = re.search(r'TASK_TYPE:\s*(\w+)', analysis, re.IGNORECASE)
        if match:
            task_type = match.group(1).lower()
            if task_type in WORKFLOW_TEMPLATES:
                return task_type
        return "general"

    def _parse_tasks_from_plan(self, plan_text: str) -> List[Dict]:
        """Parse tasks from plan text."""
        tasks = []
        task_pattern = r'\d+\.\s+(.+?)(?:\n\s*-\s*Filename:\s*(.+?))?(?:\n\s*-\s*Purpose:\s*(.+?))?(?=\n\n|\n\d+\.|\Z)'

        matches = re.finditer(task_pattern, plan_text, re.DOTALL)

        for idx, match in enumerate(matches, 1):
            description = match.group(1).strip()
            filename = match.group(2).strip() if match.group(2) else f"task_{idx}.py"
            purpose = match.group(3).strip() if match.group(3) else description

            # Determine language from filename
            ext = filename.split('.')[-1]
            language_map = {
                'py': 'python', 'js': 'javascript', 'ts': 'typescript',
                'java': 'java', 'cpp': 'cpp', 'go': 'go', 'rs': 'rust'
            }
            language = language_map.get(ext, 'python')

            tasks.append({
                'description': description,
                'filename': filename,
                'purpose': purpose,
                'language': language
            })

        if not tasks:
            # Fallback: create single task
            tasks = [{
                'description': 'Implementation',
                'filename': 'main.py',
                'purpose': plan_text[:200],
                'language': 'python'
            }]

        return tasks

    # ==================== Prompt Building Methods ====================

    def _build_supervisor_prompt(self) -> str:
        """Build supervisor analysis prompt."""
        return """You are a Supervisor Agent analyzing user requests for a PARALLEL EXECUTION system.

Analyze the request and output:

TASK_TYPE: [code_generation|bug_fix|refactoring|test_generation|code_review|general]

REASONING: [Why this type? Can tasks be parallelized?]

COMPLEXITY: [simple|moderate|complex]

PARALLEL_POTENTIAL: [high|medium|low]

Task types:
- code_generation: New features (HIGH parallel potential)
- bug_fix: Fix bugs (LOW parallel - focused)
- refactoring: Improve structure (MEDIUM parallel)
- test_generation: Create tests (HIGH parallel)
- code_review: Review code (HIGH parallel)
- general: Chat/questions (NO parallel)

Analyze carefully."""

    def _build_planning_prompt(self, user_request: str, analysis: str) -> str:
        """Build planning prompt for parallel execution."""
        return f"""You are a Planning Agent creating plans for PARALLEL EXECUTION.

User Request: {user_request}

Analysis: {analysis}

Create a detailed plan optimized for parallel execution:

## Overview
[Brief solution description]

## Tasks (Design for parallel execution)
1. Task 1 Description
   - Filename: example.py
   - Purpose: [What this does]
   - Dependencies: [None or which tasks must complete first]

2. Task 2 Description
   - Filename: another.py
   - Purpose: [What this does]
   - Dependencies: [None or which tasks must complete first]

## Parallel Execution Strategy
[How tasks can be executed concurrently]

## Dependencies
[Task dependencies for coordination]

## Testing Strategy
[Verification approach]

IMPORTANT: Design tasks to minimize dependencies for maximum parallelism."""

    def _build_parallel_coding_prompt(
        self,
        task: Dict,
        user_request: str,
        plan: str,
        agent_id: str,
        task_num: int,
        total_tasks: int
    ) -> str:
        """Build coding prompt with parallel execution context."""
        return f"""You are {agent_id}, part of a PARALLEL CODING TEAM.

**PARALLEL EXECUTION CONTEXT:**
- You are one of {total_tasks} agents working CONCURRENTLY
- Other agents are working on related tasks simultaneously
- Use SharedContext for coordination (not implemented in prompt, handled by framework)

**YOUR SPECIFIC TASK ({task_num}/{total_tasks}):**
Description: {task.get('description')}
Filename: {task.get('filename')}
Purpose: {task.get('purpose', 'N/A')}

**ORIGINAL REQUEST:**
{user_request}

**OVERALL PLAN:**
{plan}

**REQUIREMENTS:**
1. Implement ONLY your assigned task
2. Write clean, production-ready code
3. Include proper error handling
4. Add clear comments
5. Use type hints (Python) or types (TypeScript)
6. Assume other agents handle their tasks

**OUTPUT:**
Provide only the code for {task.get('filename')}, no markdown formatting."""

    def _build_coding_prompt(
        self,
        task: Dict,
        user_request: str,
        plan: str
    ) -> str:
        """Build standard coding prompt (non-parallel)."""
        return f"""You are a Coding Agent implementing a task.

User Request: {user_request}

Overall Plan:
{plan}

Current Task: {task.get('description')}
Filename: {task.get('filename')}

Implement with:
1. Clean, production-ready code
2. Proper error handling
3. Clear comments
4. Type hints where applicable

Output only the code, no markdown."""

    def _build_review_prompt(
        self,
        shared_context: SharedContext,
        user_request: str
    ) -> str:
        """Build review prompt with shared context."""
        entries = shared_context.get_entries_summary()

        files_summary = "\n".join([
            f"- {entry['agent_id']}: {entry.get('description', 'Code output')}"
            for entry in entries
        ])

        return f"""You are a Review Agent evaluating a PARALLEL IMPLEMENTATION.

User Request: {user_request}

Implemented Files (from parallel agents):
{files_summary}

Total Agents: {len(entries)}

Review for:
1. Correctness: Does it solve the problem?
2. Quality: Clean and maintainable?
3. Integration: Do parallel outputs work together?
4. Completeness: All requirements met?
5. Improvements: Any suggestions?

Provide structured review."""


# ==================== Manager Class ====================

class DeepAgentWorkflowManagerV2:
    """Manager for hybrid DeepAgent workflow sessions."""

    def __init__(self):
        self.workflows: Dict[str, DeepAgentWorkflowManager] = {}
        logger.info("Hybrid DeepAgent Workflow Manager initialized")

    def get_or_create_workflow(
        self,
        session_id: str,
        workspace: str = "/home/user/workspace"
    ) -> DeepAgentWorkflowManager:
        """Get existing or create new workflow for session."""
        if session_id not in self.workflows:
            self.workflows[session_id] = DeepAgentWorkflowManager(
                agent_id=f"hybrid_{session_id}",
                workspace=workspace,
                enable_parallel=True,
                max_parallel_agents=25
            )
            logger.info(f"Created hybrid workflow for session {session_id}")
        return self.workflows[session_id]

    def delete_workflow(self, session_id: str) -> None:
        """Delete workflow for session."""
        if session_id in self.workflows:
            del self.workflows[session_id]
            logger.info(f"Deleted workflow for session {session_id}")
