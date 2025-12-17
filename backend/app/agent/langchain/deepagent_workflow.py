"""
DeepAgent-based Workflow Manager

This module provides a workflow manager that uses the DeepAgents framework
for advanced middleware capabilities including:
- TodoListMiddleware: Built-in task tracking
- SubAgentMiddleware: Isolated sub-agent execution
- SummarizationMiddleware: Automatic context compression
- FilesystemMiddleware: Persistent conversation state

Supports the same interface as the standard LangChain workflow manager.
"""
import asyncio
import json
import os
from typing import Dict, Any, List, Optional, AsyncGenerator
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

try:
    from deepagents import create_deep_agent
    from deepagents.middleware import (
        TodoListMiddleware,
        SubAgentMiddleware,
        SummarizationMiddleware,
        FilesystemMiddleware
    )
    DEEPAGENTS_AVAILABLE = True
except ImportError:
    DEEPAGENTS_AVAILABLE = False
    print("Warning: DeepAgents not available. Install with: pip install deepagents tavily-python")

from app.core.config import settings
from app.agent.base.interface import BaseWorkflow


class DeepAgentWorkflowManager(BaseWorkflow):
    """
    Workflow manager using DeepAgents framework for advanced capabilities.

    Features:
    - TodoListMiddleware: Structured task tracking with automatic updates
    - SubAgentMiddleware: Isolated execution contexts for cleaner state
    - SummarizationMiddleware: Auto-compression at 170k tokens
    - FilesystemMiddleware: Persistent conversation backend
    """

    def __init__(
        self,
        agent_id: str = "deepagent_workflow",
        model_name: str = "gpt-4o",
        temperature: float = 0.7,
        enable_todos: bool = True,
        enable_subagents: bool = True,
        enable_summarization: bool = True,
        enable_filesystem: bool = True,
        workspace: str = "/home/user/workspace"
    ):
        """
        Initialize DeepAgent workflow manager.

        Args:
            agent_id: Unique identifier for this agent
            model_name: OpenAI model to use
            temperature: Model temperature
            enable_todos: Enable TodoListMiddleware
            enable_subagents: Enable SubAgentMiddleware
            enable_summarization: Enable SummarizationMiddleware
            enable_filesystem: Enable FilesystemMiddleware
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

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=settings.OPENAI_API_KEY,
            streaming=True
        )

        # Build middleware stack
        self.middleware_stack = []

        if enable_filesystem:
            # Persistent conversation backend
            fs_path = os.path.join(workspace, '.deepagents', agent_id)
            os.makedirs(fs_path, exist_ok=True)
            self.middleware_stack.append(
                FilesystemMiddleware(base_path=fs_path)
            )

        if enable_summarization:
            # Auto-compress at 170k tokens
            self.middleware_stack.append(
                SummarizationMiddleware(
                    threshold_tokens=170000,
                    llm=self.llm
                )
            )

        if enable_subagents:
            # Isolated sub-agent execution
            self.middleware_stack.append(
                SubAgentMiddleware(llm=self.llm)
            )

        if enable_todos:
            # Built-in task tracking
            self.middleware_stack.append(
                TodoListMiddleware()
            )

        # Create DeepAgent with middleware stack
        self.agent = create_deep_agent(
            llm=self.llm,
            middleware=self.middleware_stack,
            agent_id=agent_id
        )

        # Task tracking (integrated with TodoListMiddleware)
        self.current_todos = []

    async def execute_workflow(
        self,
        user_request: str,
        session_id: str,
        workspace: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute workflow with DeepAgents middleware.

        Args:
            user_request: User's request
            session_id: Session identifier
            workspace: Optional workspace override

        Yields:
            Workflow updates compatible with frontend
        """
        if workspace:
            self.workspace = workspace

        try:
            # Phase 1: Supervisor Analysis
            yield {
                "agent": "SupervisorAgent",
                "type": "thinking",
                "status": "running",
                "message": "🧠 Analyzing request with DeepAgents framework...",
                "timestamp": datetime.now().isoformat()
            }

            # Build supervisor prompt
            supervisor_prompt = self._build_supervisor_prompt(user_request)

            # Execute with DeepAgent (TodoListMiddleware will track tasks)
            analysis_result = ""
            async for chunk in self.agent.astream([
                SystemMessage(content=supervisor_prompt),
                HumanMessage(content=user_request)
            ]):
                if chunk.content:
                    analysis_result += chunk.content

                    # Check for todo updates from TodoListMiddleware
                    if hasattr(chunk, 'metadata') and 'todos' in chunk.metadata:
                        todos = chunk.metadata['todos']
                        yield {
                            "agent": "TodoManager",
                            "type": "todo_update",
                            "status": "running",
                            "todos": todos,
                            "timestamp": datetime.now().isoformat()
                        }

            # Parse analysis
            task_type = self._parse_task_type(analysis_result)

            yield {
                "agent": "SupervisorAgent",
                "type": "analysis",
                "status": "completed",
                "message": f"✅ Task classified as: {task_type}",
                "analysis": analysis_result,
                "task_type": task_type,
                "timestamp": datetime.now().isoformat()
            }

            # Phase 2: Execute based on task type
            if task_type in ["code_generation", "bug_fix", "refactoring"]:
                async for update in self._execute_coding_workflow(
                    user_request, analysis_result, session_id
                ):
                    yield update
            else:
                # General chat mode
                async for update in self._execute_chat_mode(
                    user_request, session_id
                ):
                    yield update

            # Final completion
            yield {
                "agent": "DeepAgent",
                "type": "completion",
                "status": "completed",
                "message": "✅ Workflow completed successfully",
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            yield {
                "agent": "DeepAgent",
                "type": "error",
                "status": "error",
                "message": f"❌ Error: {str(e)}",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def _execute_coding_workflow(
        self,
        user_request: str,
        analysis: str,
        session_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute coding workflow using SubAgentMiddleware for isolated execution."""

        # Phase 1: Planning
        yield {
            "agent": "PlanningAgent",
            "type": "thinking",
            "status": "running",
            "message": "📋 Creating implementation plan...",
            "timestamp": datetime.now().isoformat()
        }

        planning_prompt = self._build_planning_prompt(user_request, analysis)

        plan_text = ""
        async for chunk in self.agent.astream([
            SystemMessage(content=planning_prompt),
            HumanMessage(content=user_request)
        ]):
            if chunk.content:
                plan_text += chunk.content

        # Parse tasks from plan
        tasks = self._parse_tasks_from_plan(plan_text)

        yield {
            "agent": "PlanningAgent",
            "type": "plan",
            "status": "completed",
            "message": f"✅ Plan created with {len(tasks)} tasks",
            "plan": plan_text,
            "tasks": tasks,
            "timestamp": datetime.now().isoformat()
        }

        # Phase 2: Implementation (using SubAgentMiddleware for isolation)
        yield {
            "agent": "CodingAgent",
            "type": "thinking",
            "status": "running",
            "message": f"🔨 Implementing {len(tasks)} tasks with isolated sub-agents...",
            "timestamp": datetime.now().isoformat()
        }

        # Execute tasks with SubAgentMiddleware
        completed_tasks = []
        for idx, task in enumerate(tasks):
            task_num = idx + 1

            yield {
                "agent": "CodingAgent",
                "type": "task_start",
                "status": "running",
                "message": f"📝 Task {task_num}/{len(tasks)}: {task.get('description', 'Processing...')}",
                "task_num": task_num,
                "total_tasks": len(tasks),
                "timestamp": datetime.now().isoformat()
            }

            # SubAgentMiddleware creates isolated context
            coding_prompt = self._build_coding_prompt(task, user_request, plan_text)

            code_output = ""
            async for chunk in self.agent.astream([
                SystemMessage(content=coding_prompt),
                HumanMessage(content=f"Implement: {task.get('description')}")
            ], context_isolation=True):  # SubAgentMiddleware feature
                if chunk.content:
                    code_output += chunk.content

            # Extract filename and code
            filename = task.get('filename', f'task_{task_num}.py')

            completed_tasks.append({
                'task_num': task_num,
                'description': task.get('description'),
                'filename': filename,
                'code': code_output
            })

            # Emit artifact
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

        # Phase 3: Review
        yield {
            "agent": "ReviewAgent",
            "type": "thinking",
            "status": "running",
            "message": "🔍 Reviewing implementation...",
            "timestamp": datetime.now().isoformat()
        }

        review_prompt = self._build_review_prompt(completed_tasks, user_request)

        review_text = ""
        async for chunk in self.agent.astream([
            SystemMessage(content=review_prompt),
            HumanMessage(content="Review the implementation")
        ]):
            if chunk.content:
                review_text += chunk.content

        yield {
            "agent": "ReviewAgent",
            "type": "review",
            "status": "completed",
            "message": "✅ Review completed",
            "review": review_text,
            "timestamp": datetime.now().isoformat()
        }

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
            "message": "💬 Processing your question...",
            "timestamp": datetime.now().isoformat()
        }

        response = ""
        async for chunk in self.agent.astream([
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

    def _build_supervisor_prompt(self, user_request: str) -> str:
        """Build supervisor analysis prompt."""
        return """You are a Supervisor Agent that analyzes user requests and determines the appropriate workflow.

Analyze the request and output in this format:

TASK_TYPE: [code_generation|bug_fix|refactoring|documentation|testing|general]

REASONING: [Brief explanation of why this task type was chosen]

COMPLEXITY: [simple|moderate|complex]

Available task types:
- code_generation: Creating new code/features
- bug_fix: Fixing existing bugs
- refactoring: Improving code structure
- documentation: Writing docs
- testing: Creating tests
- general: Questions, explanations, discussions

Analyze the following request carefully."""

    def _build_planning_prompt(self, user_request: str, analysis: str) -> str:
        """Build planning prompt."""
        return f"""You are a Planning Agent that creates detailed implementation plans.

User Request: {user_request}

Analysis: {analysis}

Create a detailed plan with the following structure:

## Overview
[Brief description of the solution]

## Tasks
1. Task 1 Description
   - Filename: example.py
   - Purpose: [What this accomplishes]

2. Task 2 Description
   - Filename: another.py
   - Purpose: [What this accomplishes]

## Dependencies
[Any dependencies or prerequisites]

## Testing Strategy
[How to verify the implementation]

Be specific and actionable."""

    def _build_coding_prompt(self, task: Dict, user_request: str, plan: str) -> str:
        """Build coding prompt for individual task."""
        return f"""You are a Coding Agent implementing a specific task.

User Request: {user_request}

Overall Plan:
{plan}

Current Task: {task.get('description')}
Filename: {task.get('filename')}

Implement this task with:
1. Clean, production-ready code
2. Proper error handling
3. Clear comments
4. Type hints where applicable

Output only the code, no markdown formatting."""

    def _build_review_prompt(self, tasks: List[Dict], user_request: str) -> str:
        """Build review prompt."""
        task_summary = "\n".join([
            f"- {t['filename']}: {t['description']}"
            for t in tasks
        ])

        return f"""You are a Review Agent evaluating the implementation.

User Request: {user_request}

Implemented Files:
{task_summary}

Review the implementation for:
1. Correctness: Does it solve the problem?
2. Quality: Is the code clean and maintainable?
3. Completeness: Are all requirements met?
4. Improvements: Any suggestions?

Provide a structured review."""

    def _parse_task_type(self, analysis: str) -> str:
        """Parse task type from supervisor analysis."""
        import re

        match = re.search(r'TASK_TYPE:\s*(\w+)', analysis, re.IGNORECASE)
        if match:
            return match.group(1).lower()

        # Fallback keyword matching
        text_lower = analysis.lower()
        if 'code_generation' in text_lower or 'create new' in text_lower:
            return 'code_generation'
        elif 'bug' in text_lower or 'fix' in text_lower:
            return 'bug_fix'
        elif 'refactor' in text_lower:
            return 'refactoring'

        return 'general'

    def _parse_tasks_from_plan(self, plan: str) -> List[Dict[str, Any]]:
        """Parse individual tasks from plan text."""
        tasks = []

        # Simple regex-based parsing
        import re
        task_matches = re.findall(
            r'(\d+)\.\s+(.+?)\n\s*-\s*Filename:\s*(.+?)\n',
            plan,
            re.MULTILINE
        )

        for match in task_matches:
            task_num, description, filename = match
            tasks.append({
                'task_num': int(task_num),
                'description': description.strip(),
                'filename': filename.strip(),
                'language': self._detect_language(filename.strip())
            })

        # Fallback if no tasks parsed
        if not tasks:
            tasks.append({
                'task_num': 1,
                'description': 'Implement solution',
                'filename': 'solution.py',
                'language': 'python'
            })

        return tasks

    def _detect_language(self, filename: str) -> str:
        """Detect programming language from filename."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
        }

        for ext, lang in ext_map.items():
            if filename.endswith(ext):
                return lang

        return 'python'  # default

    async def get_conversation_state(self, session_id: str) -> Dict[str, Any]:
        """Get conversation state from FilesystemMiddleware."""
        if hasattr(self.agent, 'get_state'):
            return await self.agent.get_state(session_id)
        return {}

    async def save_conversation_state(
        self,
        session_id: str,
        state: Dict[str, Any]
    ) -> None:
        """Save conversation state to FilesystemMiddleware."""
        if hasattr(self.agent, 'save_state'):
            await self.agent.save_state(session_id, state)
