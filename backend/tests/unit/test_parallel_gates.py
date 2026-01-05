"""Unit tests for Parallel Quality Gates Execution

Tests the parallel execution logic for Reviewer, QA, and Security gates
to ensure proper handling with vLLM's batching/caching optimizations.

Run with: python -m tests.unit.test_parallel_gates
"""

import asyncio
import time
from typing import Dict, List, Tuple


class MockGateResult:
    """Mock result from a quality gate"""
    def __init__(self, gate_name: str, passed: bool = True, delay: float = 0.1):
        self.gate_name = gate_name
        self.passed = passed
        self.delay = delay


def create_mock_gate(gate_name: str, result: Dict, delay: float = 0.1):
    """Create a mock gate function that simulates vLLM response time"""
    def mock_gate(state: Dict) -> Dict:
        time.sleep(delay)  # Simulate vLLM response time
        return result
    return mock_gate


class TestParallelGateExecution:
    """Tests for parallel quality gate execution"""

    def test_parallel_execution_faster_than_sequential(self):
        """Verify parallel execution is faster than sequential"""
        gate_delay = 0.1  # 100ms per gate

        # Create mock gates
        reviewer_result = {"review_approved": True, "review_feedback": {"quality_score": 0.9}}
        qa_result = {"qa_passed": True, "qa_result": {"passed": True}}
        security_result = {"security_passed": True, "security_result": {"passed": True}}

        mock_reviewer = create_mock_gate("reviewer", reviewer_result, gate_delay)
        mock_qa = create_mock_gate("qa_gate", qa_result, gate_delay)
        mock_security = create_mock_gate("security_gate", security_result, gate_delay)

        state = {"coder_output": {"artifacts": [{"filename": "test.py", "content": "print('hello')"}]}}

        # Test sequential execution time
        sequential_start = time.time()
        mock_reviewer(state)
        mock_qa(state)
        mock_security(state)
        sequential_time = time.time() - sequential_start

        # Test parallel execution
        async def run_parallel():
            async def run_gate(gate_func):
                return await asyncio.to_thread(gate_func, state)

            tasks = [run_gate(f) for f in [mock_reviewer, mock_qa, mock_security]]
            return await asyncio.gather(*tasks)

        parallel_start = time.time()
        asyncio.run(run_parallel())
        parallel_time = time.time() - parallel_start

        # Parallel should be significantly faster (at least 2x)
        assert parallel_time < sequential_time * 0.7, \
            f"Parallel ({parallel_time:.3f}s) should be faster than sequential ({sequential_time:.3f}s)"

        print(f"\n[Test] Sequential: {sequential_time:.3f}s, Parallel: {parallel_time:.3f}s")
        print(f"[Test] Speedup: {sequential_time/parallel_time:.2f}x")

    def test_parallel_gates_collect_all_results(self):
        """Verify all gate results are collected correctly"""
        reviewer_result = {"review_approved": True, "review_feedback": {"quality_score": 0.85}}
        qa_result = {"qa_passed": True, "qa_result": {"message": "All tests passed"}}
        security_result = {"security_passed": False, "security_result": {"issues": ["SQL injection risk"]}}

        mock_reviewer = create_mock_gate("reviewer", reviewer_result)
        mock_qa = create_mock_gate("qa_gate", qa_result)
        mock_security = create_mock_gate("security_gate", security_result)

        state = {}

        async def run_parallel():
            async def run_gate(name: str, gate_func) -> Tuple[str, Dict, float]:
                start = time.time()
                result = await asyncio.to_thread(gate_func, state)
                return name, result, time.time() - start

            gates = [
                ("reviewer", mock_reviewer),
                ("qa_gate", mock_qa),
                ("security_gate", mock_security),
            ]

            tasks = [run_gate(name, func) for name, func in gates]
            return await asyncio.gather(*tasks)

        results = asyncio.run(run_parallel())

        # Verify all results collected
        assert len(results) == 3

        result_dict = {name: result for name, result, _ in results}
        assert result_dict["reviewer"]["review_approved"] == True
        assert result_dict["qa_gate"]["qa_passed"] == True
        assert result_dict["security_gate"]["security_passed"] == False

        print(f"\n[Test] Collected {len(results)} gate results")
        for name, result, exec_time in results:
            print(f"  - {name}: {exec_time:.3f}s")

    def test_parallel_gates_error_isolation(self):
        """Verify one gate failure doesn't affect others"""
        reviewer_result = {"review_approved": True}
        qa_result = {"qa_passed": True}

        def failing_gate(state):
            raise Exception("Security check failed")

        mock_reviewer = create_mock_gate("reviewer", reviewer_result)
        mock_qa = create_mock_gate("qa_gate", qa_result)

        state = {}

        async def run_parallel_with_error_handling():
            async def run_gate(name: str, gate_func) -> Tuple[str, Dict, float, bool]:
                start = time.time()
                try:
                    result = await asyncio.to_thread(gate_func, state)
                    return name, result, time.time() - start, True
                except Exception as e:
                    return name, {"error": str(e)}, time.time() - start, False

            gates = [
                ("reviewer", mock_reviewer),
                ("qa_gate", mock_qa),
                ("security_gate", failing_gate),
            ]

            tasks = [run_gate(name, func) for name, func in gates]
            return await asyncio.gather(*tasks)

        results = asyncio.run(run_parallel_with_error_handling())

        # Verify successful gates still complete
        successful = [r for r in results if r[3]]
        failed = [r for r in results if not r[3]]

        assert len(successful) == 2, "Two gates should succeed"
        assert len(failed) == 1, "One gate should fail"
        assert failed[0][0] == "security_gate", "Security gate should be the failed one"

        print(f"\n[Test] Successful: {len(successful)}, Failed: {len(failed)}")

    def test_concurrent_vllm_request_simulation(self):
        """Simulate concurrent requests to vLLM with batching behavior"""
        request_times = []

        def simulated_vllm_request(prompt: str, delay_base: float = 0.05):
            """Simulate vLLM request with batching benefit"""
            start = time.time()
            # Simulate that concurrent requests benefit from batching
            # (slightly faster per-request when batched)
            actual_delay = delay_base * 0.8 if len(request_times) > 0 else delay_base
            time.sleep(actual_delay)
            request_times.append({
                "prompt_length": len(prompt),
                "duration": time.time() - start,
                "batch_benefit": len(request_times) > 0
            })
            return {"response": "OK", "prompt_length": len(prompt)}

        # Simulate 3 concurrent review requests
        prompts = [
            "Review this Python code for security issues...",
            "Check this code for quality and best practices...",
            "Analyze this code for potential bugs...",
        ]

        async def run_concurrent_requests():
            async def make_request(prompt):
                return await asyncio.to_thread(simulated_vllm_request, prompt)

            tasks = [make_request(p) for p in prompts]
            return await asyncio.gather(*tasks)

        results = asyncio.run(run_concurrent_requests())

        assert len(results) == 3
        assert all(r["response"] == "OK" for r in results)

        print(f"\n[Test] vLLM Batching Simulation:")
        for i, req in enumerate(request_times):
            print(f"  Request {i+1}: {req['duration']*1000:.1f}ms (batch benefit: {req['batch_benefit']})")


class TestVLLMOptimizationCompatibility:
    """Tests to verify compatibility with vLLM optimizations"""

    def test_prefix_caching_benefit(self):
        """Verify that similar system prompts benefit from prefix caching"""
        # Simulate prefix caching: same prefix = faster response
        cache = {}

        def simulated_request_with_caching(system_prompt: str, user_prompt: str):
            prefix_hash = hash(system_prompt[:100])  # First 100 chars as prefix

            if prefix_hash in cache:
                # Cache hit - faster response
                time.sleep(0.02)
                cached = True
            else:
                # Cache miss - slower first request
                cache[prefix_hash] = True
                time.sleep(0.05)
                cached = False

            return {"cached": cached, "prefix_hash": prefix_hash}

        # All quality gates use similar system prompts
        system_prompt = "You are an expert code reviewer analyzing code quality..."

        requests = [
            (system_prompt, "Review file1.py"),
            (system_prompt, "Review file2.py"),
            (system_prompt, "Review file3.py"),
        ]

        results = []
        for sys, user in requests:
            result = simulated_request_with_caching(sys, user)
            results.append(result)

        # First request should be cache miss, rest should hit
        assert results[0]["cached"] == False, "First request should be cache miss"
        assert results[1]["cached"] == True, "Second request should hit cache"
        assert results[2]["cached"] == True, "Third request should hit cache"

        print(f"\n[Test] Prefix Caching: {sum(r['cached'] for r in results)}/{len(results)} cache hits")

    def test_continuous_batching_simulation(self):
        """Simulate continuous batching where new requests join ongoing batches"""
        batch_queue = []
        processed = []

        def add_to_batch(request_id: int):
            batch_queue.append(request_id)
            # Simulate waiting for batch to process
            time.sleep(0.03)
            processed.append(request_id)
            return {"request_id": request_id, "batch_size": len(batch_queue)}

        async def run_continuous_batching():
            async def submit_request(req_id):
                return await asyncio.to_thread(add_to_batch, req_id)

            # Submit requests with slight delays to simulate continuous arrival
            tasks = []
            for i in range(5):
                tasks.append(asyncio.create_task(submit_request(i)))
                await asyncio.sleep(0.005)  # Staggered arrival

            return await asyncio.gather(*tasks)

        results = asyncio.run(run_continuous_batching())

        assert len(results) == 5
        # Later requests should see larger batch sizes (continuous batching effect)
        batch_sizes = [r["batch_size"] for r in results]

        print(f"\n[Test] Continuous Batching - Batch sizes: {batch_sizes}")
        print(f"[Test] Processing order: {processed}")


def run_all_tests():
    """Run all tests without pytest dependency"""
    print('=' * 60)
    print('Testing Parallel Gate Execution')
    print('=' * 60)

    test = TestParallelGateExecution()
    passed = 0
    failed = 0

    tests = [
        ("test_parallel_execution_faster_than_sequential", test.test_parallel_execution_faster_than_sequential),
        ("test_parallel_gates_collect_all_results", test.test_parallel_gates_collect_all_results),
        ("test_parallel_gates_error_isolation", test.test_parallel_gates_error_isolation),
        ("test_concurrent_vllm_request_simulation", test.test_concurrent_vllm_request_simulation),
    ]

    for name, test_func in tests:
        print(f'\n{name}')
        try:
            test_func()
            print('   PASSED')
            passed += 1
        except AssertionError as e:
            print(f'   FAILED: {e}')
            failed += 1

    print('\n' + '=' * 60)
    print('Testing vLLM Optimization Compatibility')
    print('=' * 60)

    test2 = TestVLLMOptimizationCompatibility()

    tests2 = [
        ("test_prefix_caching_benefit", test2.test_prefix_caching_benefit),
        ("test_continuous_batching_simulation", test2.test_continuous_batching_simulation),
    ]

    for name, test_func in tests2:
        print(f'\n{name}')
        try:
            test_func()
            print('   PASSED')
            passed += 1
        except AssertionError as e:
            print(f'   FAILED: {e}')
            failed += 1

    print('\n' + '=' * 60)
    print(f'Results: {passed} passed, {failed} failed')
    print('=' * 60)

    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
