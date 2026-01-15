"""Test Observability System

Demonstrates:
1. StructuredLogger - JSONL logging
2. DecisionTracker - Agent decisions
3. ToolLogger - Tool call tracking
4. MetricsCollector - Performance metrics
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from observability import (
    StructuredLogger,
    LogLevel,
    get_logger,
    DecisionTracker,
    Decision,
    ToolLogger,
    ToolCall,
    MetricsCollector,
    Metric,
    MetricType,
)


def test_structured_logger():
    """Test StructuredLogger"""
    print("=" * 60)
    print("Testing StructuredLogger")
    print("=" * 60)

    # Create logger
    print("\n1. Creating structured logger...")
    logger = StructuredLogger(
        log_file="/tmp/test_logs.jsonl",
        console_output=True
    )
    print("   ✅ Logger created")

    # Test basic logging
    print("\n2. Testing basic logging...")
    logger.debug("Debug message", context="test")
    logger.info("Info message", user="test_user")
    logger.warning("Warning message", threshold=0.8)
    logger.error("Error message", error_code=500)
    print("   ✅ Basic logging works")

    # Test workflow logging
    print("\n3. Testing workflow logging...")
    logger.log_workflow("coding", "started", task_id="task_123")
    logger.log_workflow("coding", "completed", task_id="task_123", duration=45.5)
    print("   ✅ Workflow logging works")

    # Test agent logging
    print("\n4. Testing agent logging...")
    logger.log_agent("planner", "workflow", "started", iteration=1)
    logger.log_agent("executor", "sub_agent", "completed", success=True)
    print("   ✅ Agent logging works")

    # Test task logging
    print("\n5. Testing task logging...")
    logger.log_task("task_456", "created", priority="high")
    logger.log_task("task_456", "assigned", agent="executor")
    print("   ✅ Task logging works")

    # Test global logger
    print("\n6. Testing global logger...")
    global_logger = get_logger(log_file="/tmp/test_global.jsonl")
    global_logger.info("Global logger test")
    print("   ✅ Global logger works")

    print()


def test_decision_tracker():
    """Test DecisionTracker"""
    print("=" * 60)
    print("Testing DecisionTracker")
    print("=" * 60)

    # Create tracker
    print("\n1. Creating decision tracker...")
    tracker = DecisionTracker(
        log_file="/tmp/test_decisions.jsonl",
        auto_save=True
    )
    print("   ✅ Tracker created")

    # Record decisions
    print("\n2. Recording decisions...")
    decision1 = tracker.record_decision(
        agent_name="planner",
        agent_type="workflow",
        decision_type="plan",
        decision="Execute 3 sequential steps",
        reasoning="Task complexity requires structured approach",
        alternatives=["Parallel execution", "Single step"],
        confidence=0.85,
        context={"task": "build_app"}
    )
    print(f"   Decision 1: {decision1.decision_id}")

    decision2 = tracker.record_decision(
        agent_name="executor",
        agent_type="sub_agent",
        decision_type="execute",
        decision="Use read_file tool",
        reasoning="Need to inspect current code",
        confidence=0.95
    )
    print(f"   Decision 2: {decision2.decision_id}")
    print("   ✅ Decision recording works")

    # Update outcome
    print("\n3. Updating decision outcome...")
    tracker.update_outcome(decision1.decision_id, "success")
    print("   ✅ Outcome update works")

    # Get decisions
    print("\n4. Retrieving decisions...")
    all_decisions = tracker.get_decisions()
    planner_decisions = tracker.get_decisions(agent_name="planner")
    print(f"   Total: {len(all_decisions)}")
    print(f"   Planner: {len(planner_decisions)}")
    print("   ✅ Decision retrieval works")

    # Get stats
    print("\n5. Getting statistics...")
    stats = tracker.get_stats()
    print(f"   Total decisions: {stats['total_decisions']}")
    print(f"   By type: {stats['by_type']}")
    print(f"   Avg confidence: {stats['avg_confidence']:.2f}")
    print("   ✅ Statistics works")

    print()


def test_tool_logger():
    """Test ToolLogger"""
    print("=" * 60)
    print("Testing ToolLogger")
    print("=" * 60)

    # Create logger
    print("\n1. Creating tool logger...")
    logger = ToolLogger(
        log_file="/tmp/test_tools.jsonl",
        auto_save=True
    )
    print("   ✅ Logger created")

    # Test start/end pattern
    print("\n2. Testing start/end pattern...")
    call_id = logger.start_call(
        tool_name="read_file",
        agent_name="code_reader",
        parameters={"file_path": "/path/to/file.py"}
    )
    print(f"   Started call: {call_id}")

    # Simulate tool execution
    time.sleep(0.1)

    logger.end_call(
        call_id=call_id,
        result="file contents here",
        success=True,
        duration=0.1
    )
    print("   ✅ Start/end pattern works")

    # Test direct logging
    print("\n3. Testing direct logging...")
    logger.log_call(
        tool_name="write_file",
        agent_name="code_writer",
        parameters={"file_path": "/path/to/output.py", "content": "code"},
        result="Success",
        success=True,
        duration=0.05
    )
    logger.log_call(
        tool_name="execute_python",
        agent_name="code_tester",
        parameters={"code": "print('hello')"},
        success=False,
        error="Syntax error",
        duration=0.02
    )
    print("   ✅ Direct logging works")

    # Get tool calls
    print("\n4. Retrieving tool calls...")
    all_calls = logger.get_calls()
    read_calls = logger.get_calls(tool_name="read_file")
    successful_calls = logger.get_calls(success_only=True)
    print(f"   Total: {len(all_calls)}")
    print(f"   Read file: {len(read_calls)}")
    print(f"   Successful: {len(successful_calls)}")
    print("   ✅ Tool call retrieval works")

    # Get stats
    print("\n5. Getting statistics...")
    stats = logger.get_stats()
    print(f"   Total calls: {stats['total_calls']}")
    print(f"   By tool: {stats['by_tool']}")
    print(f"   Success rate: {stats['success_rate']:.1%}")
    print(f"   Avg duration: {stats['avg_duration']:.3f}s")
    print("   ✅ Statistics works")

    print()


def test_metrics_collector():
    """Test MetricsCollector"""
    print("=" * 60)
    print("Testing MetricsCollector")
    print("=" * 60)

    # Create collector
    print("\n1. Creating metrics collector...")
    collector = MetricsCollector(
        log_file="/tmp/test_metrics.jsonl",
        auto_save=True
    )
    print("   ✅ Collector created")

    # Test counters
    print("\n2. Testing counters...")
    collector.increment("workflow.executions", tags={"domain": "coding"})
    collector.increment("workflow.executions", tags={"domain": "coding"})
    collector.increment("workflow.executions", tags={"domain": "research"})
    collector.counter("api.requests", 5)
    print("   ✅ Counters work")

    # Test gauges
    print("\n3. Testing gauges...")
    collector.gauge("active.agents", 3, unit="count")
    collector.gauge("memory.usage", 512.5, unit="MB")
    print("   ✅ Gauges work")

    # Test histograms
    print("\n4. Testing histograms...")
    for i in range(5):
        collector.histogram("response.time", 0.1 + i * 0.05, unit="seconds")
    print("   ✅ Histograms work")

    # Test timers
    print("\n5. Testing timers...")
    collector.timer("llm.call.duration", 1.5, tags={"model": "gpt-oss-120b"})
    collector.timer("llm.call.duration", 2.3, tags={"model": "gpt-oss-120b"})
    print("   ✅ Timers work")

    # Get counter values
    print("\n6. Getting counter values...")
    coding_count = collector.get_counter_value(
        "workflow.executions",
        tags={"domain": "coding"}
    )
    print(f"   Coding workflows: {coding_count}")
    print("   ✅ Counter retrieval works")

    # Get stats
    print("\n7. Getting statistics...")
    timer_stats = collector.get_stats(name="llm.call.duration")
    print(f"   LLM calls: {timer_stats['count']}")
    print(f"   Min: {timer_stats['min']:.2f}s")
    print(f"   Max: {timer_stats['max']:.2f}s")
    print(f"   Mean: {timer_stats['mean']:.2f}s")
    print("   ✅ Statistics works")

    # Get summary
    print("\n8. Getting summary...")
    summary = collector.get_summary()
    print(f"   Total metrics: {summary['total_metrics']}")
    print(f"   By type: {summary['by_type']}")
    print("   ✅ Summary works")

    print()


def test_integration():
    """Test integration of all components"""
    print("=" * 60)
    print("Testing Observability Integration")
    print("=" * 60)

    print("\n1. Setting up observability stack...")

    # Initialize all components
    logger = StructuredLogger(log_file="/tmp/integration_logs.jsonl")
    decision_tracker = DecisionTracker(log_file="/tmp/integration_decisions.jsonl")
    tool_logger = ToolLogger(log_file="/tmp/integration_tools.jsonl")
    metrics = MetricsCollector(log_file="/tmp/integration_metrics.jsonl")

    print("   ✅ All components initialized")

    print("\n2. Simulating workflow execution...")

    # Log workflow start
    logger.log_workflow("coding", "started", task_id="task_integration")
    metrics.increment("workflow.started", tags={"domain": "coding"})

    # Record planning decision
    decision = decision_tracker.record_decision(
        agent_name="planner",
        agent_type="workflow",
        decision_type="plan",
        decision="Read files, analyze, write report",
        reasoning="Systematic approach needed",
        confidence=0.9
    )

    # Log tool call
    call_id = tool_logger.start_call(
        tool_name="read_file",
        agent_name="executor",
        parameters={"file_path": "/test.py"}
    )
    time.sleep(0.05)
    tool_logger.end_call(call_id, result="contents", success=True, duration=0.05)

    # Record metrics
    metrics.timer("tool.execution", 0.05, tags={"tool": "read_file"})
    metrics.increment("tool.calls", tags={"tool": "read_file"})

    # Update decision outcome
    decision_tracker.update_outcome(decision.decision_id, "success")

    # Log workflow completion
    logger.log_workflow("coding", "completed", task_id="task_integration", duration=10.5)
    metrics.increment("workflow.completed", tags={"domain": "coding"})
    metrics.timer("workflow.duration", 10.5, tags={"domain": "coding"})

    print("   ✅ Workflow simulation complete")

    print("\n3. Collecting statistics...")
    decision_stats = decision_tracker.get_stats()
    tool_stats = tool_logger.get_stats()
    metrics_summary = metrics.get_summary()

    print(f"   Decisions: {decision_stats['total_decisions']}")
    print(f"   Tool calls: {tool_stats['total_calls']}")
    print(f"   Metrics: {metrics_summary['total_metrics']}")
    print("   ✅ Integration test complete")

    print()


def main():
    """Run all tests"""
    print()
    print("=" * 60)
    print("Observability System Tests")
    print("=" * 60)
    print()

    try:
        # Run tests
        test_structured_logger()
        test_decision_tracker()
        test_tool_logger()
        test_metrics_collector()
        test_integration()

        print("=" * 60)
        print("✅ All observability tests passed!")
        print("=" * 60)
        print()

        print("Usage Example:")
        print("-" * 60)
        print("""
from observability import (
    get_logger, DecisionTracker, ToolLogger, MetricsCollector
)

# Initialize observability
logger = get_logger(log_file="logs/agent.jsonl")
decisions = DecisionTracker(log_file="logs/decisions.jsonl")
tools = ToolLogger(log_file="logs/tools.jsonl")
metrics = MetricsCollector(log_file="logs/metrics.jsonl")

# Log workflow
logger.log_workflow("coding", "started", task_id="task_123")

# Track decision
decisions.record_decision(
    agent_name="planner",
    agent_type="workflow",
    decision_type="plan",
    decision="Use 3-step approach",
    reasoning="Task complexity",
    confidence=0.85
)

# Log tool call
call_id = tools.start_call(
    tool_name="read_file",
    agent_name="executor",
    parameters={"file_path": "/test.py"}
)
# ... execute tool ...
tools.end_call(call_id, result="success", success=True, duration=0.5)

# Record metrics
metrics.increment("workflow.executions")
metrics.timer("workflow.duration", 45.5)
        """)
        print("-" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
