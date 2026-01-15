"""Agents Module for Agentic 2.0

Sub-agent spawning and coordination:
- SubAgent: Individual specialized agents
- SubAgentManager: Spawning and coordination
- TaskDecomposer: Complex task breakdown
- ParallelExecutor: Concurrent execution
- ResultAggregator: Result combination
"""

from .sub_agent import SubAgent, SubAgentType, SubAgentConfig
from .sub_agent_manager import SubAgentManager
from .task_decomposer import TaskDecomposer, TaskBreakdown
from .parallel_executor import ParallelExecutor, ExecutionResult
from .result_aggregator import ResultAggregator, AggregationStrategy

__all__ = [
    "SubAgent",
    "SubAgentType",
    "SubAgentConfig",
    "SubAgentManager",
    "TaskDecomposer",
    "TaskBreakdown",
    "ParallelExecutor",
    "ExecutionResult",
    "ResultAggregator",
    "AggregationStrategy",
]
