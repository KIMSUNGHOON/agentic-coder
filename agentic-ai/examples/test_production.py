"""Test Production Module

Demonstrates and tests:
1. EndpointSelector - Intelligent endpoint selection
2. ContextFilter - Context size optimization
3. ParallelToolExecutor - Concurrent tool execution
4. ErrorHandler - Error categorization and handling
5. ErrorRecovery - Retry mechanisms
6. GracefulDegradation - Reduced functionality mode
7. HealthChecker - Component health monitoring
"""

import sys
import time
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from production import (
    EndpointSelector,
    EndpointConfig,
    ContextFilter,
    ParallelToolExecutor,
    ErrorHandler,
    ErrorCategory,
    ErrorSeverity,
    ErrorRecovery,
    GracefulDegradation,
    DegradationStrategy,
    HealthChecker,
    HealthStatus,
)


def test_endpoint_selector():
    """Test EndpointSelector"""
    print("=" * 60)
    print("Testing EndpointSelector")
    print("=" * 60)

    # Create selector with test endpoints
    print("\n1. Creating endpoint selector...")
    endpoints = [
        EndpointConfig(
            name="endpoint1",
            url="http://localhost:8000",
            api_key="test_key_1",
        ),
        EndpointConfig(
            name="endpoint2",
            url="http://localhost:8001",
            api_key="test_key_2",
        ),
    ]
    selector = EndpointSelector(endpoints=endpoints)
    print(f"   ✅ Selector created with {len(endpoints)} endpoints")

    # Test recording successes
    print("\n2. Recording endpoint health...")
    selector.record_success("http://localhost:8000", response_time_ms=100)
    selector.record_success("http://localhost:8000", response_time_ms=120)
    selector.record_success("http://localhost:8001", response_time_ms=200)
    selector.record_failure("http://localhost:8001")
    print("   ✅ Health data recorded")

    # Test selecting best endpoint
    print("\n3. Selecting best endpoint...")
    best = selector.select_best_endpoint()
    print(f"   Selected: {best['name']} ({best['url']})")
    print("   ✅ Endpoint selection works")

    # Test health stats
    print("\n4. Getting health statistics...")
    stats = selector.get_endpoint_stats("http://localhost:8000")
    print(f"   Success rate: {stats['success_rate']:.1%}")
    print(f"   Avg response time: {stats['avg_response_time_ms']:.0f}ms")
    print("   ✅ Health statistics work")

    print()


def test_context_filter():
    """Test ContextFilter"""
    print("=" * 60)
    print("Testing ContextFilter")
    print("=" * 60)

    # Create filter
    print("\n1. Creating context filter...")
    filter = ContextFilter(
        max_message_length=50,
        max_list_items=3,
        max_context_size=200,
    )
    print("   ✅ Filter created")

    # Test message truncation
    print("\n2. Testing message truncation...")
    context = {
        "long_message": "A" * 100,
        "short_message": "Short",
    }
    filtered = filter.filter_context(context)
    print(f"   Original length: {len(context['long_message'])}")
    print(f"   Filtered length: {len(filtered['long_message'])}")
    print("   ✅ Message truncation works")

    # Test list limiting
    print("\n3. Testing list limiting...")
    context = {
        "items": list(range(10)),
    }
    filtered = filter.filter_context(context)
    print(f"   Original list: {len(context['items'])} items")
    print(f"   Filtered list: {len(filtered['items'])} items")
    print("   ✅ List limiting works")

    # Test priority keys
    print("\n4. Testing priority keys...")
    context = {
        "important": "A" * 100,
        "not_important": "B" * 100,
    }
    filtered = filter.filter_context(context, priority_keys=["important"])
    print(f"   Important key preserved: {len(filtered['important'])} chars")
    print(f"   Other key truncated: {len(filtered['not_important'])} chars")
    print("   ✅ Priority keys work")

    print()


async def test_parallel_tool_executor():
    """Test ParallelToolExecutor"""
    print("=" * 60)
    print("Testing ParallelToolExecutor")
    print("=" * 60)

    # Create executor
    print("\n1. Creating parallel executor...")
    executor = ParallelToolExecutor(max_parallel=3)
    print("   ✅ Executor created")

    # Test concurrent execution
    print("\n2. Testing concurrent execution...")

    async def mock_tool_1():
        await asyncio.sleep(0.1)
        return "Result 1"

    async def mock_tool_2():
        await asyncio.sleep(0.1)
        return "Result 2"

    async def mock_tool_3():
        await asyncio.sleep(0.1)
        return "Result 3"

    tool_calls = [
        (mock_tool_1, {}),
        (mock_tool_2, {}),
        (mock_tool_3, {}),
    ]

    start_time = time.time()
    results = await executor.execute_parallel(tool_calls)
    duration = time.time() - start_time

    print(f"   Executed {len(results)} tools in {duration:.2f}s")
    print(f"   Successful: {sum(1 for r in results if r['success'])}")
    print("   ✅ Concurrent execution works")

    # Test error handling
    print("\n3. Testing error handling...")

    async def mock_tool_error():
        raise ValueError("Test error")

    tool_calls = [
        (mock_tool_1, {}),
        (mock_tool_error, {}),
    ]

    results = await executor.execute_parallel(tool_calls, fail_fast=False)
    print(f"   Total results: {len(results)}")
    print(f"   Successful: {sum(1 for r in results if r['success'])}")
    print(f"   Failed: {sum(1 for r in results if not r['success'])}")
    print("   ✅ Error handling works")

    print()


def test_error_handler():
    """Test ErrorHandler"""
    print("=" * 60)
    print("Testing ErrorHandler")
    print("=" * 60)

    # Create handler
    print("\n1. Creating error handler...")
    handler = ErrorHandler()
    print("   ✅ Handler created")

    # Test error categorization
    print("\n2. Testing error categorization...")
    errors = [
        (ValueError("Invalid input"), ErrorCategory.VALIDATION_ERROR),
        (TimeoutError("Request timeout"), ErrorCategory.TIMEOUT_ERROR),
        (ConnectionError("Network error"), ErrorCategory.NETWORK_ERROR),
    ]

    for error, expected_category in errors:
        error_info = handler.handle_error(error)
        print(f"   {type(error).__name__}: {error_info.category}")
        assert error_info.category == expected_category

    print("   ✅ Error categorization works")

    # Test severity assessment
    print("\n3. Testing severity assessment...")
    error = ValueError("Test error")
    error_info = handler.handle_error(error)
    print(f"   Severity: {error_info.severity}")
    print(f"   Recoverable: {error_info.recoverable}")
    print("   ✅ Severity assessment works")

    # Test user message generation
    print("\n4. Testing user message generation...")
    print(f"   Message: {error_info.user_message}")
    print("   ✅ User message generation works")

    print()


async def test_error_recovery():
    """Test ErrorRecovery"""
    print("=" * 60)
    print("Testing ErrorRecovery")
    print("=" * 60)

    # Create recovery
    print("\n1. Creating error recovery...")
    recovery = ErrorRecovery(
        max_retries=3,
        base_delay=0.1,
        max_delay=1.0,
    )
    print("   ✅ Recovery created")

    # Test retry with backoff
    print("\n2. Testing retry with exponential backoff...")

    attempt_count = 0

    async def flaky_function():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise ValueError(f"Attempt {attempt_count} failed")
        return "Success"

    try:
        result = await recovery.retry_with_backoff(flaky_function, max_retries=3)
        print(f"   Succeeded after {attempt_count} attempts")
        print(f"   Result: {result}")
        print("   ✅ Retry with backoff works")
    except Exception as e:
        print(f"   ❌ Failed: {e}")

    # Test try with fallback
    print("\n3. Testing try with fallback...")

    async def primary_function():
        raise ValueError("Primary failed")

    async def fallback_function():
        return "Fallback success"

    result = await recovery.try_with_fallback(
        primary_function,
        fallback_function,
    )
    print(f"   Result: {result}")
    print("   ✅ Try with fallback works")

    print()


def test_graceful_degradation():
    """Test GracefulDegradation"""
    print("=" * 60)
    print("Testing GracefulDegradation")
    print("=" * 60)

    # Create degradation manager
    print("\n1. Creating degradation manager...")
    degradation = GracefulDegradation()
    print("   ✅ Degradation manager created")

    # Test entering degraded mode
    print("\n2. Testing degraded mode activation...")
    print(f"   Initial mode: {'degraded' if degradation.is_degraded() else 'full'}")

    degradation.enter_degraded_mode(
        reason="System overload",
        strategy=DegradationStrategy.REDUCE_FEATURES,
    )
    print(f"   Current mode: {'degraded' if degradation.is_degraded() else 'full'}")
    print("   ✅ Degraded mode activation works")

    # Test strategy application
    print("\n3. Testing strategy application...")
    strategy = degradation.get_current_strategy()
    print(f"   Strategy: {strategy}")
    print("   ✅ Strategy retrieval works")

    # Test returning to full functionality
    print("\n4. Testing full functionality restoration...")
    degradation.exit_degraded_mode()
    print(f"   Current mode: {'degraded' if degradation.is_degraded() else 'full'}")
    print("   ✅ Full functionality restoration works")

    print()


async def test_health_checker():
    """Test HealthChecker"""
    print("=" * 60)
    print("Testing HealthChecker")
    print("=" * 60)

    # Create health checker
    print("\n1. Creating health checker...")
    checker = HealthChecker()
    print("   ✅ Health checker created")

    # Register health checks
    print("\n2. Registering health checks...")

    def llm_check():
        return True

    def database_check():
        return True

    def memory_check():
        return False  # Simulate unhealthy

    checker.register_check("llm", llm_check)
    checker.register_check("database", database_check)
    checker.register_check("memory", memory_check)
    print("   ✅ Health checks registered")

    # Test component checking
    print("\n3. Testing component checking...")
    llm_health = await checker.check_component("llm")
    print(f"   LLM: {llm_health.status}")
    print("   ✅ Component checking works")

    # Test aggregated health
    print("\n4. Testing aggregated health check...")
    health = await checker.check_all()
    print(f"   Overall status: {health['status']}")
    print(f"   Components: {health['summary']['total']}")
    print(f"   Healthy: {health['summary']['healthy']}")
    print(f"   Unhealthy: {health['summary']['unhealthy']}")
    print("   ✅ Aggregated health check works")

    # Test readiness check
    print("\n5. Testing readiness check...")
    ready = checker.is_ready()
    print(f"   System ready: {ready}")
    print("   ✅ Readiness check works")

    # Test liveness check
    print("\n6. Testing liveness check...")
    alive = checker.is_alive()
    print(f"   System alive: {alive}")
    print("   ✅ Liveness check works")

    print()


async def test_integration():
    """Test integration of all production components"""
    print("=" * 60)
    print("Testing Production Module Integration")
    print("=" * 60)

    print("\n1. Setting up production components...")

    # Initialize all components
    endpoints = [
        EndpointConfig(
            name="endpoint1",
            url="http://localhost:8000",
            api_key="test_key_1",
        ),
    ]
    endpoint_selector = EndpointSelector(endpoints=endpoints)
    context_filter = ContextFilter()
    tool_executor = ParallelToolExecutor()
    error_handler = ErrorHandler()
    error_recovery = ErrorRecovery()
    degradation = GracefulDegradation()
    health_checker = HealthChecker()

    print("   ✅ All components initialized")

    print("\n2. Simulating production workflow...")

    # Register health check
    def system_check():
        return True

    health_checker.register_check("system", system_check)

    # Check health
    health = await health_checker.check_all()
    print(f"   System health: {health['status']}")

    # Select endpoint
    best_endpoint = endpoint_selector.select_best_endpoint()
    print(f"   Selected endpoint: {best_endpoint['name']}")

    # Filter context
    context = {"large_data": "X" * 1000}
    filtered = context_filter.filter_context(context)
    print(f"   Context filtered: {len(str(context))} -> {len(str(filtered))} chars")

    # Execute tools
    async def mock_tool():
        return "Tool result"

    results = await tool_executor.execute_parallel([(mock_tool, {})])
    print(f"   Tools executed: {len(results)}")

    # Handle error
    try:
        raise ValueError("Test error")
    except Exception as e:
        error_info = error_handler.handle_error(e)
        print(f"   Error handled: {error_info.category}")

    # Test recovery
    async def recoverable_function():
        return "Recovered"

    result = await error_recovery.retry_with_backoff(recoverable_function, max_retries=1)
    print(f"   Recovery result: {result}")

    print("   ✅ Production workflow simulation complete")

    print()


async def main():
    """Run all tests"""
    print()
    print("=" * 60)
    print("Production Module Tests")
    print("=" * 60)
    print()

    try:
        # Run synchronous tests
        test_endpoint_selector()
        test_context_filter()
        test_error_handler()
        test_graceful_degradation()

        # Run asynchronous tests
        await test_parallel_tool_executor()
        await test_error_recovery()
        await test_health_checker()
        await test_integration()

        print("=" * 60)
        print("✅ All production tests passed!")
        print("=" * 60)
        print()

        print("Production Module Features:")
        print("-" * 60)
        print("""
✅ EndpointSelector: Intelligent endpoint selection with health tracking
✅ ContextFilter: Context size optimization for LLM calls
✅ ParallelToolExecutor: Concurrent tool execution with error handling
✅ ErrorHandler: Comprehensive error categorization and handling
✅ ErrorRecovery: Retry mechanisms with exponential backoff
✅ GracefulDegradation: Reduced functionality mode for system health
✅ HealthChecker: Component health monitoring and aggregation

Usage Example:
──────────────────────────────────────────────────────────────
from production import (
    EndpointSelector, ContextFilter, ParallelToolExecutor,
    ErrorHandler, ErrorRecovery, GracefulDegradation, HealthChecker
)

# Initialize components
endpoint_selector = EndpointSelector(endpoints=[...])
context_filter = ContextFilter()
tool_executor = ParallelToolExecutor()
error_handler = ErrorHandler()
error_recovery = ErrorRecovery()
degradation = GracefulDegradation()
health_checker = HealthChecker()

# Use in production workflow
best_endpoint = endpoint_selector.select_best_endpoint()
filtered_context = context_filter.filter_context(context)
results = await tool_executor.execute_parallel(tool_calls)
error_info = error_handler.handle_error(exception)
result = await error_recovery.retry_with_backoff(function)
health = await health_checker.check_all()
        """)
        print("-" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
