"""Base Workflow for Agentic 2.0

Provides common workflow structure using LangGraph StateGraph:
- Plan: Analyze task and create execution plan
- Execute: Run tools and operations
- Reflect: Review results and decide next steps
- Iteration control: Continue or complete

All domain workflows inherit from this base class.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage

from core.state import (
    AgenticState,
    TaskStatus,
    increment_iteration,
    update_task_status,
    add_error,
)
from core.llm_client import DualEndpointLLMClient
from core.tool_safety import ToolSafetyManager
from core.optimization import get_llm_cache, get_state_optimizer, get_performance_monitor
from tools import FileSystemTools, GitTools, ProcessTools, SearchTools

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    """Result of workflow execution"""
    success: bool
    output: Any
    error: Optional[str] = None
    iterations: int = 0
    metadata: Optional[Dict[str, Any]] = None


class BaseWorkflow:
    """Base class for all workflows

    Provides common LangGraph structure:
    - StateGraph with standard nodes
    - Iteration control
    - Tool access
    - Error handling

    Subclasses implement domain-specific logic:
    - plan_node()
    - execute_node()
    - reflect_node()

    Example:
        >>> class CodingWorkflow(BaseWorkflow):
        ...     async def plan_node(self, state):
        ...         # Coding-specific planning
        ...         return state
        >>>
        >>> workflow = CodingWorkflow(llm_client, safety, tools)
        >>> result = await workflow.run(state)
    """

    def __init__(
        self,
        llm_client: DualEndpointLLMClient,
        safety_manager: ToolSafetyManager,
        workspace: Optional[str] = None,
    ):
        """Initialize BaseWorkflow

        Args:
            llm_client: LLM client for AI operations
            safety_manager: Safety manager for tool validation
            workspace: Working directory (optional)
        """
        self.llm_client = llm_client
        self.safety = safety_manager
        self.workspace = workspace

        # Initialize tools
        self.fs_tools = FileSystemTools(safety_manager, workspace)
        self.git_tools = GitTools(safety_manager)
        self.process_tools = ProcessTools(safety_manager)
        self.search_tools = SearchTools(safety_manager, workspace)

        # Build state graph
        self.graph = self._build_graph()

        logger.info(f"🔄 {self.__class__.__name__} initialized")

    def _build_graph(self) -> StateGraph:
        """Build LangGraph StateGraph

        Creates workflow graph with Phase 5 sub-agent support:
        START → plan → check_complexity → [route based on complexity]
                                           ├─ spawn_sub_agents → END (if complex)
                                           └─ execute → reflect → should_continue? (if simple/moderate)
                                                                   ↓              ↓
                                                                 END        → execute

        Returns:
            Compiled StateGraph
        """
        # Create graph
        workflow = StateGraph(AgenticState)

        # Add nodes (Phase 5: Added complexity check and sub-agent spawning)
        workflow.add_node("plan", self.plan_node)
        workflow.add_node("check_complexity", self.check_complexity_node)
        workflow.add_node("spawn_sub_agents", self.spawn_sub_agents_node)
        workflow.add_node("execute", self.execute_node)
        workflow.add_node("reflect", self.reflect_node)

        # Set entry point
        workflow.set_entry_point("plan")

        # Add edges
        workflow.add_edge("plan", "check_complexity")

        # Conditional edge from check_complexity (Phase 5 routing)
        workflow.add_conditional_edges(
            "check_complexity",
            self._route_based_on_complexity,
            {
                "spawn_sub_agents": "spawn_sub_agents",  # Complex task → sub-agents
                "execute": "execute",                     # Simple/moderate → normal execution
            }
        )

        # Sub-agents complete → END
        workflow.add_edge("spawn_sub_agents", END)

        # Normal execution path
        workflow.add_edge("execute", "reflect")

        # Conditional edge from reflect
        workflow.add_conditional_edges(
            "reflect",
            self.should_continue,
            {
                "continue": "execute",  # Continue iteration
                "end": END,             # Complete workflow
            }
        )

        # Compile graph
        compiled = workflow.compile()

        logger.info("✅ StateGraph compiled (with Phase 5 sub-agent support)")
        return compiled

    def _route_based_on_complexity(self, state: AgenticState) -> str:
        """Route based on complexity check result

        Args:
            state: Current workflow state

        Returns:
            "spawn_sub_agents" if complex, "execute" otherwise
        """
        use_sub_agents = state.get("use_sub_agents", False)

        if use_sub_agents:
            logger.info("🌟 Routing to sub-agent spawning (complex task)")
            return "spawn_sub_agents"
        else:
            logger.info("✅ Routing to normal execution (simple/moderate task)")
            return "execute"

    # ===== Node Implementations (to be overridden) =====

    async def plan_node(self, state: AgenticState) -> AgenticState:
        """Plan node: Analyze task and create execution plan

        This method should be overridden by subclasses.

        Args:
            state: Current workflow state

        Returns:
            Updated state with plan
        """
        logger.info(f"📋 Planning task: {state['task_description'][:100]}")

        # Default implementation: basic planning
        # Subclasses should override with domain-specific logic

        state["iteration"] = 0
        state["task_status"] = TaskStatus.IN_PROGRESS.value

        return state

    async def execute_node(self, state: AgenticState) -> AgenticState:
        """Execute node: Run tools and operations

        This method should be overridden by subclasses.

        Args:
            state: Current workflow state

        Returns:
            Updated state with execution results
        """
        logger.info(f"⚙️  Executing iteration {state['iteration']}")

        # Default implementation: placeholder
        # Subclasses should override with domain-specific logic

        # Increment iteration
        state = increment_iteration(state)

        return state

    async def reflect_node(self, state: AgenticState) -> AgenticState:
        """Reflect node: Review results and decide next steps

        This method should be overridden by subclasses.

        Args:
            state: Current workflow state

        Returns:
            Updated state with reflection results
        """
        logger.info(f"🤔 Reflecting on iteration {state['iteration']}")

        # Default implementation: simple reflection
        # Subclasses should override with domain-specific logic

        # Check if max iterations reached
        if state["iteration"] >= state["max_iterations"]:
            state["should_continue"] = False
            logger.warning(f"⚠️  Max iterations reached: {state['max_iterations']}")
        else:
            # Default: continue one more iteration then stop
            state["should_continue"] = state["iteration"] < 2

        return state

    async def check_complexity_node(self, state: AgenticState) -> AgenticState:
        """Check if task requires sub-agent decomposition (Phase 5)

        This node analyzes task complexity and decides whether to:
        - Execute directly (simple/moderate tasks)
        - Spawn sub-agents (complex tasks)

        Args:
            state: Current workflow state

        Returns:
            Updated state with complexity_check_done flag
        """
        logger.info("📊 Checking task complexity for sub-agent spawning")

        try:
            # Check if sub-agents are enabled in config
            sub_agent_config = state.get("context", {}).get("sub_agent_config", {})
            enabled = sub_agent_config.get("enabled", False)

            if not enabled:
                logger.info("⏭️  Sub-agents disabled, proceeding with normal execution")
                state["use_sub_agents"] = False
                state["complexity_check_done"] = True
                return state

            # Get complexity threshold from config (default: 0.7)
            complexity_threshold = sub_agent_config.get("complexity_threshold", 0.7)

            # Estimate task complexity using LLM
            complexity_score = await self._estimate_complexity(
                state["task_description"],
                state.get("context", {})
            )

            logger.info(f"📊 Task complexity: {complexity_score:.2f} (threshold: {complexity_threshold})")

            # Decide if sub-agents should be spawned
            if complexity_score >= complexity_threshold:
                logger.info("🌟 Complex task detected - will spawn sub-agents")
                state["use_sub_agents"] = True
                state["complexity_score"] = complexity_score
            else:
                logger.info("✅ Task complexity acceptable - normal execution")
                state["use_sub_agents"] = False
                state["complexity_score"] = complexity_score

            state["complexity_check_done"] = True
            return state

        except Exception as e:
            logger.error(f"❌ Complexity check error: {e}")
            # On error, proceed with normal execution (safe fallback)
            state["use_sub_agents"] = False
            state["complexity_check_done"] = True
            return state

    async def spawn_sub_agents_node(self, state: AgenticState) -> AgenticState:
        """Spawn and execute sub-agents for complex tasks (Phase 5)

        This node:
        1. Decomposes task into subtasks
        2. Spawns specialized sub-agents
        3. Executes sub-agents in parallel
        4. Aggregates results

        Args:
            state: Current workflow state

        Returns:
            Updated state with sub-agent results
        """
        logger.info("🌟 Spawning sub-agents for complex task")

        try:
            # Import sub-agent manager
            from agents.sub_agent_manager import SubAgentManager

            # Get max concurrent from config
            sub_agent_config = state.get("context", {}).get("sub_agent_config", {})
            max_concurrent = sub_agent_config.get("max_concurrent", 3)

            # Create sub-agent manager
            manager = SubAgentManager(
                llm_client=self.llm_client,
                safety_checker=self.safety,
                workspace=self.workspace or "/tmp",
                max_parallel=max_concurrent
            )

            # Execute with sub-agents
            logger.info(f"🚀 Executing with sub-agents (max_parallel={max_concurrent})")

            result = await manager.execute_with_subagents(
                task_description=state["task_description"],
                context=state.get("context", {}),
                force_decompose=False
            )

            # Update state with results
            state["task_status"] = TaskStatus.COMPLETED.value if result.success else TaskStatus.FAILED.value
            state["task_result"] = result.combined_result
            state["should_continue"] = False

            # Add metadata
            if "sub_agent_results" not in state["context"]:
                state["context"]["sub_agent_results"] = {}

            state["context"]["sub_agent_results"] = {
                "success": result.success,
                "success_count": result.success_count,
                "failure_count": result.failure_count,
                "total_subtasks": len(result.individual_results),
                "duration_seconds": result.total_duration_seconds,
                "summary": result.summary,
                "errors": result.errors,
            }

            logger.info(
                f"✅ Sub-agent execution complete: {result.success_count}/{len(result.individual_results)} succeeded, "
                f"duration: {result.total_duration_seconds:.2f}s"
            )

            return state

        except Exception as e:
            logger.error(f"❌ Sub-agent execution error: {e}", exc_info=True)
            # Fall back to normal execution
            state["task_status"] = TaskStatus.FAILED.value
            state["task_error"] = f"Sub-agent execution failed: {e}"
            state["should_continue"] = False
            return state

    async def _estimate_complexity(
        self,
        task_description: str,
        context: Dict[str, Any]
    ) -> float:
        """Estimate task complexity (0.0 - 1.0)

        Uses LLM to estimate complexity based on:
        - Number of components needed
        - Technical scope (frontend/backend/db/tests)
        - Lines of code estimate
        - Number of files needed

        Args:
            task_description: Task description
            context: Context information

        Returns:
            Complexity score between 0.0 and 1.0
        """
        prompt = f"""Estimate the complexity of this task on a scale of 0.0 to 1.0.

Task: {task_description}

Consider:
- 0.0-0.3: Simple task (1-2 files, single component)
- 0.4-0.6: Moderate task (3-5 files, 2-3 components)
- 0.7-0.9: Complex task (6-10 files, 4+ components, multiple systems)
- 0.9-1.0: Very complex task (10+ files, full stack, database, tests)

Factors:
- Number of files/components needed
- Technical scope (frontend, backend, database, tests, docs)
- Lines of code estimate
- Inter-dependencies between components

Respond with ONLY a single number between 0.0 and 1.0, nothing else.
Example: 0.75
"""

        try:
            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # Low temperature for consistent estimation
                max_tokens=10,
                use_cache=False
            )

            # Parse response
            score_str = response.strip().replace(",", ".")  # Handle different decimal formats
            score = float(score_str)

            # Clamp to valid range
            score = max(0.0, min(1.0, score))

            return score

        except Exception as e:
            logger.warning(f"Complexity estimation failed: {e}, defaulting to 0.5")
            return 0.5  # Default to moderate complexity on error

    def should_continue(self, state: AgenticState) -> str:
        """Conditional routing: Continue or end workflow?

        Args:
            state: Current workflow state

        Returns:
            "continue" or "end"
        """
        # Check should_continue flag
        if not state.get("should_continue", True):
            logger.info("✅ Workflow complete")
            return "end"

        # Check iteration limit
        if state["iteration"] >= state["max_iterations"]:
            logger.warning("⚠️  Max iterations reached")
            return "end"

        # Check if task completed
        if state.get("task_status") == TaskStatus.COMPLETED.value:
            logger.info("✅ Task completed")
            return "end"

        # Check if task failed
        if state.get("task_status") == TaskStatus.FAILED.value:
            logger.error("❌ Task failed")
            return "end"

        # Continue iteration
        logger.info(f"🔄 Continuing to iteration {state['iteration'] + 1}")
        return "continue"

    # ===== Helper Methods =====

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        use_cache: bool = True,
    ) -> str:
        """Call LLM with messages (with caching)

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (default: 0.7)
            max_tokens: Maximum tokens (default: 2000)
            use_cache: Use LLM response cache (default: True)

        Returns:
            LLM response content
        """
        try:
            # Get cache
            cache = get_llm_cache()

            # Define LLM function
            # Note: _call accepts messages and kwargs from cache but uses closure variables
            async def _call(msg=None, **kw):
                monitor = get_performance_monitor()
                monitor.increment("llm_calls")

                response = await self.llm_client.chat_completion(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                # CRITICAL: Handle None safely
                if not response.choices or len(response.choices) == 0:
                    raise ValueError("LLM returned empty response (no choices)")

                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("LLM returned None content")

                return content

            # Use cache if enabled
            if use_cache and temperature < 0.5:  # Only cache deterministic calls
                response = await cache.get_or_call(
                    messages,
                    _call,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                response = await _call()

            return response

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    async def run(self, state: AgenticState) -> WorkflowResult:
        """Run workflow with given state (optimized)

        Args:
            state: Initial workflow state

        Returns:
            WorkflowResult with execution results
        """
        try:
            logger.info(f"🚀 Starting workflow: {state['task_description'][:100]}")

            # Get optimizer and monitor
            optimizer = get_state_optimizer()
            monitor = get_performance_monitor()

            start_time = datetime.now()

            # Determine recursion_limit from state or use default
            # State may have recursion_limit set from config
            recursion_limit = state.get("recursion_limit", 100)

            logger.info(f"🔧 Using recursion_limit: {recursion_limit}, max_iterations: {state.get('max_iterations', 10)}")

            # Run graph with monitoring and configured recursion limit
            with monitor.measure("workflow_execution"):
                final_state = await self.graph.ainvoke(
                    state,
                    config={"recursion_limit": recursion_limit}
                )

            # Optimize final state
            final_state = optimizer.optimize(final_state)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Extract results
            success = final_state.get("task_status") == TaskStatus.COMPLETED.value
            output = final_state.get("task_result")
            error = final_state.get("task_error")
            iterations = final_state.get("iteration", 0)

            logger.info(
                f"✅ Workflow completed: {iterations} iterations, {duration:.2f}s"
            )

            # Record metrics
            monitor.record("workflow_duration", duration)
            monitor.record("workflow_iterations", iterations)

            # Create detailed metadata for debugging (Bug Fix #7)
            metadata = {
                "duration_seconds": duration,
                "workflow_domain": final_state.get("workflow_domain", "unknown"),
                "workflow_type": final_state.get("workflow_type", "unknown"),
                "tool_calls": final_state.get("tool_calls", []),
                "errors": final_state.get("errors", []),
                "context": {
                    "plan": final_state.get("context", {}).get("plan", {}),
                    "completed_steps": final_state.get("context", {}).get("completed_steps", []),
                },
            }

            logger.info(
                f"📊 Workflow stats: tool_calls={len(metadata['tool_calls'])}, "
                f"errors={len(metadata['errors'])}, "
                f"completed_steps={len(metadata['context']['completed_steps'])}"
            )

            return WorkflowResult(
                success=success,
                output=output,
                error=error,
                iterations=iterations,
                metadata=metadata,
            )

        except Exception as e:
            logger.error(f"❌ Workflow error: {e}")

            return WorkflowResult(
                success=False,
                output=None,
                error=str(e),
                iterations=state.get("iteration", 0),
            )

    async def run_stream(self, state: AgenticState):
        """Run workflow with streaming support (yields intermediate events)

        This method enables real-time streaming of workflow execution:
        - Node transitions (plan → execute → reflect)
        - LLM call events
        - Tool execution events
        - Error events

        Args:
            state: Initial workflow state

        Yields:
            Dict with event type and data:
            - type: "node_start", "node_end", "llm_start", "llm_chunk", "llm_end", "tool_start", "tool_end", "error"
            - data: Event-specific data

        Example:
            >>> async for event in workflow.run_stream(state):
            ...     if event["type"] == "llm_chunk":
            ...         print(event["data"]["content"], end="")
        """
        try:
            logger.info(f"🚀 Starting STREAMING workflow: {state['task_description'][:100]}")

            # Get optimizer and monitor
            optimizer = get_state_optimizer()
            monitor = get_performance_monitor()

            start_time = datetime.now()

            # Determine recursion_limit from state or use default
            recursion_limit = state.get("recursion_limit", 100)

            logger.info(f"🔧 Using recursion_limit: {recursion_limit}, max_iterations: {state.get('max_iterations', 10)}")

            # Yield initial event
            yield {
                "type": "workflow_start",
                "data": {
                    "task": state["task_description"],
                    "domain": state.get("workflow_domain", "unknown"),
                    "max_iterations": state.get("max_iterations", 10)
                }
            }

            # Stream graph execution using LangGraph's astream API
            final_state = None
            async for event in self.graph.astream(
                state,
                config={"recursion_limit": recursion_limit}
            ):
                # LangGraph yields events as: {node_name: state_update}
                for node_name, node_state in event.items():
                    # Get node execution details
                    iteration = node_state.get("iteration", 0)
                    max_iter = node_state.get("max_iterations", state.get("max_iterations", 10))
                    status = node_state.get("task_status", "in_progress")
                    should_continue = node_state.get("should_continue", True)

                    # Check for new LLM responses to display
                    llm_responses = node_state.get("context", {}).get("llm_responses", [])
                    if llm_responses and final_state:
                        # Check if there's a new response since last node
                        prev_responses = final_state.get("context", {}).get("llm_responses", [])
                        if len(llm_responses) > len(prev_responses):
                            # New response available
                            new_response = llm_responses[-1]
                            yield {
                                "type": "llm_response",
                                "data": {
                                    "node": node_name,
                                    "iteration": iteration,
                                    "response_preview": new_response.get("response", ""),
                                    "thinking": new_response.get("thinking", "")
                                }
                            }

                    # Check for plan creation (after plan_node)
                    if node_name == "plan":
                        plan = node_state.get("context", {}).get("plan")
                        if plan and plan != final_state.get("context", {}).get("plan") if final_state else True:
                            # New plan created
                            complexity = node_state.get("context", {}).get("classification", {}).get("estimated_complexity", "medium")
                            yield {
                                "type": "plan_created",
                                "data": {
                                    "node": node_name,
                                    "iteration": iteration,
                                    "plan": plan,
                                    "complexity": complexity
                                }
                            }

                    # Check for last action decided by LLM
                    last_action = node_state.get("context", {}).get("last_action")
                    if last_action:
                        yield {
                            "type": "action_decided",
                            "data": {
                                "node": node_name,
                                "iteration": iteration,
                                "action": last_action.get("action"),
                                "details": last_action
                            }
                        }

                    # Check for last tool execution to display
                    last_tool = node_state.get("context", {}).get("last_tool_execution")
                    if last_tool:
                        # Always show tool execution immediately
                        result_data = last_tool.get("result", {})
                        error_msg = result_data.get("error", "Unknown error") if not last_tool.get("success") else None

                        # Extract actual parameters from action_details
                        action_details = last_tool.get("action_details", {})
                        # action_details is {"action": "WRITE_FILE", "parameters": {"file_path": "...", "content": "..."}}
                        actual_params = action_details.get("parameters", action_details)

                        yield {
                            "type": "tool_executed",
                            "data": {
                                "node": node_name,
                                "iteration": iteration,
                                "tool": last_tool.get("action"),
                                "params": actual_params,  # Send extracted parameters directly
                                "action_details": action_details,  # Also send full action for reference
                                "success": last_tool.get("success", False),
                                "result": result_data,
                                "error": error_msg
                            }
                        }

                    # Yield node event with detailed information
                    yield {
                        "type": "node_executed",
                        "data": {
                            "node": node_name,
                            "iteration": iteration,
                            "max_iterations": max_iter,
                            "status": status,
                            "should_continue": should_continue,
                            "task_description": node_state.get("task_description", "")[:100]
                        }
                    }

                    # Log detailed debugging information
                    logger.debug(
                        f"Node: {node_name} | Iteration: {iteration}/{max_iter} | "
                        f"Status: {status} | Continue: {should_continue}"
                    )

                    # Track final state
                    final_state = node_state

            # Optimize final state
            if final_state:
                final_state = optimizer.optimize(final_state)
            else:
                final_state = state  # Fallback

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Extract results
            success = final_state.get("task_status") == TaskStatus.COMPLETED.value
            output = final_state.get("task_result")
            error = final_state.get("task_error")
            iterations = final_state.get("iteration", 0)

            logger.info(
                f"✅ STREAMING workflow completed: {iterations} iterations, {duration:.2f}s"
            )

            # Record metrics
            monitor.record("workflow_duration", duration)
            monitor.record("workflow_iterations", iterations)

            # Create detailed metadata
            metadata = {
                "duration_seconds": duration,
                "workflow_domain": final_state.get("workflow_domain", "unknown"),
                "workflow_type": final_state.get("workflow_type", "unknown"),
                "tool_calls": final_state.get("tool_calls", []),
                "errors": final_state.get("errors", []),
                "context": {
                    "plan": final_state.get("context", {}).get("plan", {}),
                    "completed_steps": final_state.get("context", {}).get("completed_steps", []),
                },
            }

            # Yield final result event
            yield {
                "type": "workflow_complete",
                "data": {
                    "success": success,
                    "output": output,
                    "error": error,
                    "iterations": iterations,
                    "metadata": metadata
                }
            }

        except Exception as e:
            logger.error(f"❌ STREAMING workflow error: {e}", exc_info=True)
            yield {
                "type": "workflow_error",
                "data": {
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            }

    async def run_with_task(
        self,
        task_description: str,
        task_id: str,
        workflow_domain: str,
        workspace: Optional[str] = None,
        max_iterations: int = 10,
    ) -> WorkflowResult:
        """Convenience method: Create state and run workflow

        Args:
            task_description: Task description
            task_id: Unique task ID
            workflow_domain: Workflow domain (coding, research, data, general)
            workspace: Working directory (optional)
            max_iterations: Maximum iterations (default: 10)

        Returns:
            WorkflowResult
        """
        from core.state import create_initial_state
        from core.router import WorkflowDomain

        # Create initial state
        state = create_initial_state(
            task_description=task_description,
            task_id=task_id,
            workflow_domain=WorkflowDomain(workflow_domain),
            workspace=workspace or self.workspace,
            max_iterations=max_iterations,
        )

        # Run workflow
        return await self.run(state)
