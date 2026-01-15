"""Sub-Agent Manager for Agentic 2.0

Manages dynamic sub-agent spawning and coordination:
- Sub-agent creation and lifecycle
- Task decomposition integration
- Parallel execution coordination
- Result aggregation
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.llm_client import DualEndpointLLMClient
from core.tool_safety import ToolSafetyManager
from tools import FileSystemTools, GitTools, ProcessTools, SearchTools

from .sub_agent import SubAgent, SubAgentType, SubAgentConfig
from .task_decomposer import TaskDecomposer, TaskComplexity
from .parallel_executor import ParallelExecutor
from .result_aggregator import ResultAggregator, AggregationStrategy

logger = logging.getLogger(__name__)


class SubAgentManager:
    """Manages sub-agent spawning and coordination

    Features:
    - Dynamic agent creation
    - Automatic task decomposition
    - Parallel execution
    - Result aggregation
    - Resource management

    Example:
        >>> manager = SubAgentManager(llm_client, safety_checker, "/workspace")
        >>> result = await manager.execute_with_subagents(
        ...     task_description="Analyze all Python files and generate report",
        ...     context={"project": "my_project"}
        ... )
        >>> print(result.summary)
    """

    def __init__(
        self,
        llm_client: DualEndpointLLMClient,
        safety_checker: ToolSafetyManager,
        workspace: str = "/workspace",
        max_parallel: int = 3
    ):
        """Initialize sub-agent manager

        Args:
            llm_client: LLM client for agents
            safety_checker: Safety checker for tools
            workspace: Working directory
            max_parallel: Max parallel sub-agents (default: 3)
        """
        self.llm_client = llm_client
        self.safety_checker = safety_checker
        self.workspace = workspace
        self.max_parallel = max_parallel

        # Initialize tools
        self.fs_tools = FileSystemTools(workspace, safety_checker)
        self.git_tools = GitTools(workspace, safety_checker)
        self.process_tools = ProcessTools(workspace, safety_checker)
        self.search_tools = SearchTools(workspace)

        # All available tools
        self.all_tools = {
            "read_file": self.fs_tools,
            "write_file": self.fs_tools,
            "list_directory": self.fs_tools,
            "search_files": self.fs_tools,
            "git_status": self.git_tools,
            "git_diff": self.git_tools,
            "git_log": self.git_tools,
            "execute_command": self.process_tools,
            "execute_python": self.process_tools,
            "search_code": self.search_tools,
        }

        # Initialize components
        self.decomposer = TaskDecomposer(llm_client)
        self.executor = ParallelExecutor(max_parallel=max_parallel)
        self.aggregator = ResultAggregator(llm_client)

        # Active agents registry
        self.active_agents: Dict[str, SubAgent] = {}
        self.agent_counter = 0

        logger.info(f"🎯 SubAgentManager initialized (max_parallel={max_parallel}, workspace={workspace})")

    async def execute_with_subagents(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
        force_decompose: bool = False
    ) -> Any:
        """Execute task with sub-agent spawning

        Args:
            task_description: Task to execute
            context: Optional context information
            force_decompose: Force decomposition even for simple tasks

        Returns:
            AggregatedResult with combined results
        """
        logger.info(f"🎯 Executing with sub-agents: {task_description[:100]}")

        try:
            # Step 1: Decompose task
            breakdown = await self.decomposer.decompose(task_description, context)

            logger.info(f"📋 Task complexity: {breakdown.complexity}, "
                       f"requires_decomposition: {breakdown.requires_decomposition}")

            # Check if decomposition needed
            if not breakdown.requires_decomposition and not force_decompose:
                logger.info("✅ Simple task, no sub-agents needed")
                # Return simple result
                from .result_aggregator import AggregatedResult
                return AggregatedResult(
                    original_task=task_description,
                    success=True,
                    strategy=AggregationStrategy.CONCATENATE,
                    combined_result="Task can be executed directly without sub-agents",
                    individual_results=[],
                    total_duration_seconds=0,
                    success_count=0,
                    failure_count=0,
                    summary=f"Task is simple ({breakdown.complexity}), no decomposition needed",
                    errors=[],
                    metadata={"breakdown": breakdown}
                )

            # Step 2: Spawn sub-agents for each subtask
            agent_tasks = []

            for subtask in breakdown.subtasks:
                agent = self._spawn_agent(subtask.agent_type, subtask.id)
                agent_tasks.append((agent, subtask))

            logger.info(f"🤖 Spawned {len(agent_tasks)} sub-agents")

            # Step 3: Execute based on strategy
            if breakdown.execution_strategy == "parallel":
                logger.info("🚀 Executing in parallel")
                results = await self.executor.execute_batch(agent_tasks, context)

            elif breakdown.execution_strategy == "sequential":
                logger.info("🔄 Executing sequentially")
                results = await self.executor.execute_sequential(agent_tasks, context)

            else:
                # Dependency-aware execution
                logger.info("📊 Executing with dependency awareness")
                execution_order = self.decomposer.get_execution_order(breakdown.subtasks)
                results = await self.executor.execute_with_dependencies(
                    agent_tasks,
                    execution_order,
                    context
                )

            # Step 4: Aggregate results
            aggregated = await self.aggregator.aggregate(
                results=results,
                original_task=task_description,
                strategy=AggregationStrategy.SUMMARIZE
            )

            logger.info(f"✅ Sub-agent execution complete: {aggregated.success_count}/{len(results)} succeeded")

            # Clean up agents
            self._cleanup_agents()

            return aggregated

        except Exception as e:
            logger.error(f"❌ Sub-agent execution error: {e}")
            # Return error result
            from .result_aggregator import AggregatedResult
            return AggregatedResult(
                original_task=task_description,
                success=False,
                strategy=AggregationStrategy.CONCATENATE,
                combined_result=None,
                individual_results=[],
                total_duration_seconds=0,
                success_count=0,
                failure_count=1,
                summary=f"Execution failed: {e}",
                errors=[str(e)],
                metadata={"error": str(e)}
            )

    def _spawn_agent(
        self,
        agent_type: SubAgentType,
        task_id: str
    ) -> SubAgent:
        """Spawn a new sub-agent

        Args:
            agent_type: Type of agent to spawn
            task_id: Task ID for the agent

        Returns:
            Spawned SubAgent instance
        """
        self.agent_counter += 1
        agent_name = f"{agent_type.value}_{self.agent_counter}"

        # Create agent config based on type
        config = self._create_agent_config(agent_type, agent_name, task_id)

        # Create agent
        agent = SubAgent(
            config=config,
            llm_client=self.llm_client,
            tools=self.all_tools,
            workspace=self.workspace
        )

        # Register agent
        self.active_agents[agent_name] = agent

        logger.info(f"🤖 Spawned sub-agent: {agent_name} ({agent_type})")

        return agent

    def _create_agent_config(
        self,
        agent_type: SubAgentType,
        agent_name: str,
        task_id: str
    ) -> SubAgentConfig:
        """Create configuration for agent based on type"""

        # Agent type configurations
        configs = {
            SubAgentType.CODE_READER: SubAgentConfig(
                agent_type=agent_type,
                name=agent_name,
                description="Reads and analyzes code files",
                system_prompt="You are an expert code analyzer. Read and analyze code carefully, identifying key patterns, structures, and potential issues.",
                allowed_tools=["read_file", "search_code", "list_directory"],
                temperature=0.3
            ),
            SubAgentType.CODE_WRITER: SubAgentConfig(
                agent_type=agent_type,
                name=agent_name,
                description="Writes and modifies code",
                system_prompt="You are an expert programmer. Write clean, efficient, and well-documented code following best practices.",
                allowed_tools=["read_file", "write_file", "search_code"],
                temperature=0.5
            ),
            SubAgentType.CODE_TESTER: SubAgentConfig(
                agent_type=agent_type,
                name=agent_name,
                description="Runs tests and validates code",
                system_prompt="You are a testing expert. Run tests thoroughly and report all failures and issues clearly.",
                allowed_tools=["read_file", "execute_python", "execute_command"],
                temperature=0.2
            ),
            SubAgentType.DOCUMENT_SEARCHER: SubAgentConfig(
                agent_type=agent_type,
                name=agent_name,
                description="Searches and finds documents",
                system_prompt="You are an information retrieval expert. Search for and locate relevant documents efficiently.",
                allowed_tools=["search_files", "list_directory", "read_file"],
                temperature=0.3
            ),
            SubAgentType.INFORMATION_GATHERER: SubAgentConfig(
                agent_type=agent_type,
                name=agent_name,
                description="Gathers information from various sources",
                system_prompt="You are a research assistant. Gather comprehensive information from available sources.",
                allowed_tools=["read_file", "search_files", "search_code"],
                temperature=0.4
            ),
            SubAgentType.DATA_LOADER: SubAgentConfig(
                agent_type=agent_type,
                name=agent_name,
                description="Loads and inspects data files",
                system_prompt="You are a data engineer. Load and inspect data files, reporting structure and key statistics.",
                allowed_tools=["read_file", "search_files", "list_directory"],
                temperature=0.3
            ),
            SubAgentType.DATA_ANALYZER: SubAgentConfig(
                agent_type=agent_type,
                name=agent_name,
                description="Analyzes data",
                system_prompt="You are a data analyst. Analyze data thoroughly and extract meaningful insights.",
                allowed_tools=["read_file", "execute_python"],
                temperature=0.4
            ),
            SubAgentType.FILE_ORGANIZER: SubAgentConfig(
                agent_type=agent_type,
                name=agent_name,
                description="Organizes files and directories",
                system_prompt="You are a system organizer. Organize files logically and maintain clean directory structures.",
                allowed_tools=["list_directory", "search_files", "read_file", "write_file"],
                temperature=0.3
            ),
            SubAgentType.COMMAND_RUNNER: SubAgentConfig(
                agent_type=agent_type,
                name=agent_name,
                description="Executes shell commands",
                system_prompt="You are a system administrator. Execute commands safely and report results clearly.",
                allowed_tools=["execute_command"],
                temperature=0.2
            ),
            SubAgentType.TASK_EXECUTOR: SubAgentConfig(
                agent_type=agent_type,
                name=agent_name,
                description="Executes general tasks",
                system_prompt="You are a versatile assistant. Execute tasks efficiently using available tools.",
                allowed_tools=list(self.all_tools.keys()),  # All tools available
                temperature=0.5
            ),
        }

        # Get config or default to TASK_EXECUTOR
        config = configs.get(agent_type, configs[SubAgentType.TASK_EXECUTOR])

        return config

    def _cleanup_agents(self):
        """Clean up completed agents"""
        completed = [
            name for name, agent in self.active_agents.items()
            if not agent.is_running
        ]

        for name in completed:
            del self.active_agents[name]

        if completed:
            logger.info(f"🧹 Cleaned up {len(completed)} completed agents")

    def get_active_agents(self) -> List[Dict[str, Any]]:
        """Get information about active agents"""
        return [agent.get_info() for agent in self.active_agents.values()]

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        return {
            "active_agents": len(self.active_agents),
            "total_spawned": self.agent_counter,
            "max_parallel": self.max_parallel,
            "workspace": self.workspace,
            "executor_stats": self.executor.get_stats()
        }
