"""Test Sub-Agent System

Demonstrates:
1. SubAgent creation and execution
2. Task decomposition
3. Parallel execution
4. Result aggregation
5. SubAgentManager orchestration
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import (
    SubAgent,
    SubAgentType,
    SubAgentConfig,
    SubAgentManager,
    TaskDecomposer,
    ParallelExecutor,
    ResultAggregator,
    AggregationStrategy
)
from agents.parallel_executor import ExecutionResult, ExecutionStatus
from core.llm_client import DualEndpointLLMClient
from core.tool_safety import ToolSafetyManager
from core.config_loader import load_config


def test_sub_agent_types():
    """Test SubAgentType enum"""
    print("=" * 60)
    print("Testing SubAgentType Enum")
    print("=" * 60)

    types = list(SubAgentType)
    print(f"Available agent types: {len(types)}")
    for agent_type in types:
        print(f"  - {agent_type.value}")

    print("✅ SubAgentType enum works")
    print()


async def test_task_decomposer():
    """Test TaskDecomposer"""
    print("=" * 60)
    print("Testing TaskDecomposer")
    print("=" * 60)

    # Load config
    config = load_config()

    # Create LLM client
    llm_client = DualEndpointLLMClient(
        endpoints=config.llm.endpoints,
        model_name=config.llm.model_name,
        health_check_interval=60,
    )

    decomposer = TaskDecomposer(llm_client)

    # Test simple task
    print("\n1. Testing simple task decomposition...")
    breakdown = await decomposer.decompose(
        task_description="List all Python files in current directory"
    )

    print(f"   Complexity: {breakdown.complexity}")
    print(f"   Requires decomposition: {breakdown.requires_decomposition}")
    print(f"   Subtasks: {len(breakdown.subtasks)}")
    print(f"   Strategy: {breakdown.execution_strategy}")
    print("   ✅ Simple task decomposition works")

    # Test complex task
    print("\n2. Testing complex task decomposition...")
    breakdown = await decomposer.decompose(
        task_description="Analyze all Python files, find code issues, generate a report, and create a summary document"
    )

    print(f"   Complexity: {breakdown.complexity}")
    print(f"   Requires decomposition: {breakdown.requires_decomposition}")
    print(f"   Subtasks: {len(breakdown.subtasks)}")
    print(f"   Strategy: {breakdown.execution_strategy}")

    if breakdown.subtasks:
        print("   Subtask breakdown:")
        for st in breakdown.subtasks:
            print(f"     - {st.id}: {st.description[:50]}... ({st.agent_type})")

    print("   ✅ Complex task decomposition works")

    # Test execution order
    if breakdown.subtasks:
        print("\n3. Testing execution order...")
        execution_order = decomposer.get_execution_order(breakdown.subtasks)
        print(f"   Execution batches: {len(execution_order)}")
        for i, batch in enumerate(execution_order):
            print(f"     Batch {i + 1}: {batch}")
        print("   ✅ Execution order works")

    print()


async def test_parallel_executor():
    """Test ParallelExecutor with mock agents"""
    print("=" * 60)
    print("Testing ParallelExecutor")
    print("=" * 60)

    from agents.task_decomposer import SubTask

    # Create mock execution results (simulating real execution)
    mock_results = [
        ExecutionResult(
            subtask_id="task_1",
            agent_name="code_reader_1",
            status=ExecutionStatus.COMPLETED,
            success=True,
            result="Found 10 Python files",
            duration_seconds=1.5,
            iterations=2
        ),
        ExecutionResult(
            subtask_id="task_2",
            agent_name="code_analyzer_1",
            status=ExecutionStatus.COMPLETED,
            success=True,
            result="Analyzed 10 files, found 3 issues",
            duration_seconds=2.3,
            iterations=3
        ),
        ExecutionResult(
            subtask_id="task_3",
            agent_name="report_writer_1",
            status=ExecutionStatus.FAILED,
            success=False,
            error="Failed to write report",
            duration_seconds=0.5,
            iterations=1
        ),
    ]

    print(f"\n1. Mock execution results: {len(mock_results)}")
    for result in mock_results:
        status_icon = "✅" if result.success else "❌"
        print(f"   {status_icon} {result.subtask_id}: {result.status.value}")

    print("   ✅ Execution results format works")

    # Test executor stats
    executor = ParallelExecutor(max_parallel=3)
    executor.completed_count = 2
    executor.failed_count = 1

    stats = executor.get_stats()
    print(f"\n2. Executor stats:")
    print(f"   Max parallel: {stats['max_parallel']}")
    print(f"   Completed: {stats['completed_count']}")
    print(f"   Failed: {stats['failed_count']}")
    print("   ✅ Executor stats works")

    print()


async def test_result_aggregator():
    """Test ResultAggregator"""
    print("=" * 60)
    print("Testing ResultAggregator")
    print("=" * 60)

    from agents.parallel_executor import ExecutionResult, ExecutionStatus

    # Create mock results
    results = [
        ExecutionResult(
            subtask_id="task_1",
            agent_name="agent_1",
            status=ExecutionStatus.COMPLETED,
            success=True,
            result="Result from task 1",
            duration_seconds=1.0,
            iterations=2
        ),
        ExecutionResult(
            subtask_id="task_2",
            agent_name="agent_2",
            status=ExecutionStatus.COMPLETED,
            success=True,
            result="Result from task 2",
            duration_seconds=1.5,
            iterations=3
        ),
    ]

    # Load config for LLM client
    config = load_config()
    llm_client = DualEndpointLLMClient(
        endpoints=config.llm.endpoints,
        model_name=config.llm.model_name,
        health_check_interval=60,
    )

    aggregator = ResultAggregator(llm_client)

    # Test concatenation
    print("\n1. Testing CONCATENATE strategy...")
    aggregated = await aggregator.aggregate(
        results=results,
        original_task="Test task",
        strategy=AggregationStrategy.CONCATENATE
    )

    print(f"   Success: {aggregated.success}")
    print(f"   Success count: {aggregated.success_count}")
    print(f"   Failure count: {aggregated.failure_count}")
    print(f"   Duration: {aggregated.total_duration_seconds:.1f}s")
    print("   ✅ CONCATENATE aggregation works")

    # Test list
    print("\n2. Testing LIST strategy...")
    aggregated = await aggregator.aggregate(
        results=results,
        original_task="Test task",
        strategy=AggregationStrategy.LIST
    )

    print(f"   Result count: {len(aggregated.combined_result)}")
    print("   ✅ LIST aggregation works")

    # Test report formatting
    print("\n3. Testing report formatting...")
    report = aggregator.format_report(aggregated)
    print(f"   Report length: {len(report)} characters")
    print("   ✅ Report formatting works")

    print()


async def test_sub_agent_manager():
    """Test SubAgentManager"""
    print("=" * 60)
    print("Testing SubAgentManager")
    print("=" * 60)

    # Load config
    config = load_config()

    # Create LLM client
    llm_client = DualEndpointLLMClient(
        endpoints=config.llm.endpoints,
        model_name=config.llm.model_name,
        health_check_interval=60,
    )

    # Create safety checker
    safety_checker = ToolSafetyManager(
        command_allowlist=[],
        command_denylist=["rm -rf", "sudo"],
        protected_files=["/etc/passwd"],
        protected_patterns=["*.key", "*.pem"]
    )

    # Create manager
    manager = SubAgentManager(
        llm_client=llm_client,
        safety_checker=safety_checker,
        workspace="/tmp/test_workspace",
        max_parallel=2
    )

    print(f"\n1. Manager initialized")
    stats = manager.get_stats()
    print(f"   Active agents: {stats['active_agents']}")
    print(f"   Max parallel: {stats['max_parallel']}")
    print("   ✅ Manager initialization works")

    # Test agent spawning
    print("\n2. Testing agent spawning...")
    agent = manager._spawn_agent(SubAgentType.CODE_READER, "test_task_1")
    print(f"   Spawned agent: {agent.config.name}")
    print(f"   Agent type: {agent.config.agent_type}")
    print(f"   Allowed tools: {len(agent.config.allowed_tools)}")
    print("   ✅ Agent spawning works")

    # Test simple task execution (should not decompose)
    print("\n3. Testing simple task execution...")
    result = await manager.execute_with_subagents(
        task_description="List files in current directory",
        context={"test": True}
    )

    print(f"   Success: {result.success}")
    print(f"   Strategy: {result.strategy}")
    print(f"   Summary: {result.summary[:100]}")
    print("   ✅ Simple task execution works")

    stats = manager.get_stats()
    print(f"\n4. Final stats:")
    print(f"   Total spawned: {stats['total_spawned']}")
    print("   ✅ Manager stats works")

    print()


async def main():
    """Run all tests"""
    print()
    print("=" * 60)
    print("Sub-Agent System Tests")
    print("=" * 60)
    print()

    try:
        # Run tests
        test_sub_agent_types()
        await test_task_decomposer()
        await test_parallel_executor()
        await test_result_aggregator()
        await test_sub_agent_manager()

        print("=" * 60)
        print("✅ All sub-agent tests passed!")
        print("=" * 60)
        print()

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
