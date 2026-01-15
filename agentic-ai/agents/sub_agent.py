"""Sub-Agent Module for Agentic 2.0

Provides specialized sub-agents for task execution:
- Dynamic agent creation
- Context isolation
- Tool specialization
- Independent execution
"""

import logging
import asyncio
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from core.state import AgenticState, TaskStatus, create_initial_state
from core.llm_client import DualEndpointLLMClient

logger = logging.getLogger(__name__)


class SubAgentType(str, Enum):
    """Types of specialized sub-agents"""

    # Code-related
    CODE_READER = "code_reader"  # Read and analyze code
    CODE_WRITER = "code_writer"  # Write and modify code
    CODE_TESTER = "code_tester"  # Run tests and validate

    # Research-related
    DOCUMENT_SEARCHER = "document_searcher"  # Search documents
    INFORMATION_GATHERER = "information_gatherer"  # Gather information
    REPORT_WRITER = "report_writer"  # Generate reports

    # Data-related
    DATA_LOADER = "data_loader"  # Load data files
    DATA_ANALYZER = "data_analyzer"  # Analyze data
    DATA_VISUALIZER = "data_visualizer"  # Create visualizations

    # General
    FILE_ORGANIZER = "file_organizer"  # Organize files
    TASK_EXECUTOR = "task_executor"  # Execute generic tasks
    COMMAND_RUNNER = "command_runner"  # Run shell commands


@dataclass
class SubAgentConfig:
    """Configuration for a sub-agent"""

    agent_type: SubAgentType
    name: str
    description: str
    system_prompt: str
    allowed_tools: List[str] = field(default_factory=list)
    max_iterations: int = 10
    temperature: float = 0.7
    timeout_seconds: int = 300
    context: Dict[str, Any] = field(default_factory=dict)


class SubAgent:
    """Specialized sub-agent for isolated task execution

    Features:
    - Independent context and state
    - Specialized tool access
    - Focused system prompt
    - Resource limits

    Example:
        >>> config = SubAgentConfig(
        ...     agent_type=SubAgentType.CODE_READER,
        ...     name="code_analyzer",
        ...     description="Analyzes Python code",
        ...     system_prompt="You are an expert code analyzer...",
        ...     allowed_tools=["read_file", "search_code"]
        ... )
        >>> agent = SubAgent(config, llm_client, tools)
        >>> result = await agent.execute_task("Analyze main.py")
    """

    def __init__(
        self,
        config: SubAgentConfig,
        llm_client: DualEndpointLLMClient,
        tools: Dict[str, Any],
        workspace: str = "/workspace"
    ):
        """Initialize sub-agent

        Args:
            config: Agent configuration
            llm_client: LLM client for API calls
            tools: Available tools (filtered by allowed_tools)
            workspace: Working directory
        """
        self.config = config
        self.llm_client = llm_client
        self.workspace = workspace

        # Filter tools by allowed list
        if config.allowed_tools:
            self.tools = {
                name: tool for name, tool in tools.items()
                if name in config.allowed_tools
            }
        else:
            self.tools = tools

        # State tracking
        self.created_at = datetime.now()
        self.state: Optional[AgenticState] = None
        self.is_running = False

        logger.info(f"🤖 SubAgent created: {config.name} ({config.agent_type})")

    async def execute_task(
        self,
        task_description: str,
        task_id: Optional[str] = None,
        parent_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a task with this sub-agent

        Args:
            task_description: Task to execute
            task_id: Optional task ID
            parent_context: Optional context from parent agent

        Returns:
            Execution result with status, output, errors
        """
        if self.is_running:
            return {
                "success": False,
                "error": "SubAgent is already running",
                "agent_name": self.config.name
            }

        self.is_running = True
        start_time = datetime.now()

        try:
            logger.info(f"🚀 SubAgent {self.config.name} starting task: {task_description[:100]}")

            # Create isolated state
            self.state = create_initial_state(
                task_id=task_id or f"subagent_{self.config.name}_{start_time.timestamp()}",
                task_description=task_description,
                task_type=self.config.agent_type.value,
                workspace=self.workspace,
                max_iterations=self.config.max_iterations
            )

            # Merge parent context if provided
            if parent_context:
                self.state["context"].update(parent_context)

            # Add agent config context
            self.state["context"].update(self.config.context)

            # Execute task with timeout
            try:
                result = await asyncio.wait_for(
                    self._execute_with_llm(),
                    timeout=self.config.timeout_seconds
                )

                duration = (datetime.now() - start_time).total_seconds()

                logger.info(f"✅ SubAgent {self.config.name} completed in {duration:.1f}s")

                return {
                    "success": True,
                    "agent_name": self.config.name,
                    "agent_type": self.config.agent_type.value,
                    "task_description": task_description,
                    "result": result,
                    "iterations": self.state.get("iteration", 0),
                    "duration_seconds": duration,
                    "tool_calls": self.state.get("tool_calls", []),
                    "state": self.state
                }

            except asyncio.TimeoutError:
                logger.error(f"⏱️  SubAgent {self.config.name} timed out after {self.config.timeout_seconds}s")
                return {
                    "success": False,
                    "agent_name": self.config.name,
                    "error": f"Timeout after {self.config.timeout_seconds}s",
                    "task_description": task_description,
                    "iterations": self.state.get("iteration", 0) if self.state else 0
                }

        except Exception as e:
            logger.error(f"❌ SubAgent {self.config.name} error: {e}")
            return {
                "success": False,
                "agent_name": self.config.name,
                "error": str(e),
                "task_description": task_description
            }

        finally:
            self.is_running = False

    async def _execute_with_llm(self) -> str:
        """Execute task using LLM calls

        Returns:
            Task result as string
        """
        iteration = 0
        max_iterations = self.config.max_iterations

        while iteration < max_iterations:
            # Build prompt with context
            prompt = self._build_prompt()

            messages = [
                {"role": "system", "content": self.config.system_prompt},
                {"role": "user", "content": prompt}
            ]

            # Call LLM
            response = await self.llm_client.chat_completion(
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=2000
            )

            content = response.choices[0].message.content

            # Check if task is complete
            if self._is_task_complete(content):
                self.state["task_status"] = TaskStatus.COMPLETED.value
                return content

            # Update iteration
            iteration += 1
            self.state["iteration"] = iteration

        # Max iterations reached
        self.state["task_status"] = TaskStatus.FAILED.value
        return f"Task incomplete after {max_iterations} iterations"

    def _build_prompt(self) -> str:
        """Build prompt for LLM call"""
        prompt = f"""Task: {self.state['task_description']}

Workspace: {self.workspace}
Iteration: {self.state['iteration']}/{self.config.max_iterations}
Available Tools: {', '.join(self.tools.keys())}

Context: {self.state.get('context', {})}

Please complete this task step by step. When you're done, respond with a summary starting with 'TASK_COMPLETE:'.
"""
        return prompt

    def _is_task_complete(self, response: str) -> bool:
        """Check if LLM response indicates task completion"""
        completion_markers = [
            "TASK_COMPLETE:",
            "task is complete",
            "successfully completed",
            "done",
            "finished"
        ]

        response_lower = response.lower()
        return any(marker.lower() in response_lower for marker in completion_markers)

    def get_state(self) -> Optional[AgenticState]:
        """Get current agent state"""
        return self.state

    def get_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            "name": self.config.name,
            "type": self.config.agent_type.value,
            "description": self.config.description,
            "is_running": self.is_running,
            "allowed_tools": self.config.allowed_tools,
            "max_iterations": self.config.max_iterations,
            "created_at": self.created_at.isoformat(),
            "current_iteration": self.state.get("iteration", 0) if self.state else 0
        }
