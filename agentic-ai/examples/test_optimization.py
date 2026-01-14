"""Test optimization features

Demonstrates:
1. LRU Cache with TTL
2. LLM Response Cache
3. State Optimizer
4. Performance Monitor
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.optimization import (
    LRUCache,
    LLMResponseCache,
    StateOptimizer,
    PerformanceMonitor,
)


def test_lru_cache():
    """Test LRU Cache"""
    print("=" * 60)
    print("Testing LRU Cache")
    print("=" * 60)

    cache = LRUCache(max_size=3, default_ttl=10.0)

    # Test basic operations
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")

    assert cache.get("key1") == "value1"
    assert cache.get("key2") == "value2"
    assert cache.get("key3") == "value3"

    print("✅ Basic set/get works")

    # Test LRU eviction
    cache.set("key4", "value4")  # Should evict key1 (oldest)

    assert cache.get("key1") is None  # Evicted
    assert cache.get("key2") == "value2"
    assert cache.get("key4") == "value4"

    print("✅ LRU eviction works")

    # Test stats
    stats = cache.get_stats()
    print(f"✅ Cache stats: {stats}")
    print(f"   Hit rate: {stats['hit_rate']:.2%}")
    print()


async def test_llm_cache():
    """Test LLM Response Cache"""
    print("=" * 60)
    print("Testing LLM Response Cache")
    print("=" * 60)

    cache = LLMResponseCache(max_size=10, ttl=60.0)

    # Mock LLM function
    call_count = 0

    async def mock_llm(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        return f"Response {call_count}"

    # Test caching
    messages = [{"role": "user", "content": "Hello"}]

    response1 = await cache.get_or_call(messages, mock_llm, temperature=0.3)
    response2 = await cache.get_or_call(messages, mock_llm, temperature=0.3)

    assert response1 == response2
    assert call_count == 1  # Only called once, second was cached

    print(f"✅ LLM caching works (call_count: {call_count})")

    # Test cache stats
    stats = cache.get_stats()
    print(f"✅ Cache stats: {stats}")
    print(f"   Hit rate: {stats['hit_rate']:.2%}")
    print()


def test_state_optimizer():
    """Test State Optimizer"""
    print("=" * 60)
    print("Testing State Optimizer")
    print("=" * 60)

    optimizer = StateOptimizer(
        max_messages=5,
        max_tool_calls=10,
        max_context_size_kb=50
    )

    # Create large state
    state = {
        "messages": [{"role": "user", "content": f"Message {i}"} for i in range(20)],
        "tool_calls": [{"tool": f"tool_{i}"} for i in range(30)],
        "context": {"data": "x" * 1000}
    }

    print(f"Before optimization:")
    print(f"  Messages: {len(state['messages'])}")
    print(f"  Tool calls: {len(state['tool_calls'])}")

    # Optimize
    optimized = optimizer.optimize(state)

    print(f"After optimization:")
    print(f"  Messages: {len(optimized['messages'])}")
    print(f"  Tool calls: {len(optimized['tool_calls'])}")

    assert len(optimized['messages']) <= 5
    assert len(optimized['tool_calls']) <= 10

    print("✅ State optimization works")
    print()


def test_performance_monitor():
    """Test Performance Monitor"""
    print("=" * 60)
    print("Testing Performance Monitor")
    print("=" * 60)

    monitor = PerformanceMonitor()

    # Record some metrics
    monitor.record("task_duration", 1.5)
    monitor.record("task_duration", 2.0)
    monitor.record("task_duration", 1.8)

    monitor.increment("llm_calls")
    monitor.increment("llm_calls")
    monitor.increment("llm_calls")

    # Test context manager
    import time

    with monitor.measure("operation"):
        time.sleep(0.1)

    # Get stats
    stats = monitor.get_stats()

    print("✅ Performance monitoring works")
    print(f"   Metrics: {list(stats['metrics'].keys())}")
    print(f"   Counts: {stats['counts']}")
    print(f"   Task duration mean: {stats['metrics']['task_duration']['mean']:.2f}s")
    print()


async def main():
    """Run all tests"""
    print()
    print("=" * 60)
    print("Optimization Module Tests")
    print("=" * 60)
    print()

    try:
        # Run tests
        test_lru_cache()
        await test_llm_cache()
        test_state_optimizer()
        test_performance_monitor()

        print("=" * 60)
        print("✅ All optimization tests passed!")
        print("=" * 60)
        print()

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
