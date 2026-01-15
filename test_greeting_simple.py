#!/usr/bin/env python3
"""Simple test for greeting detection - tests GeneralWorkflow directly"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add agentic-ai to path
sys.path.insert(0, str(Path(__file__).parent / "agentic-ai"))

from workflows.general_workflow import GeneralWorkflow
from core.state import create_initial_state, WorkflowDomain, TaskStatus


async def test_greeting_detection_direct():
    """Test greeting detection in GeneralWorkflow.plan_node"""
    print("=" * 80)
    print("Testing Greeting Detection (Direct GeneralWorkflow Test)")
    print("=" * 80)

    try:
        # Create mock LLM client and safety manager
        mock_llm = Mock()
        mock_safety = Mock()

        # Create GeneralWorkflow
        workflow = GeneralWorkflow(
            llm_client=mock_llm,
            safety_manager=mock_safety,
            workspace="/tmp/test"
        )

        # Test cases
        test_cases = [
            ("hello", "Simple greeting"),
            ("hi", "Short greeting"),
            ("hey there", "Casual greeting"),
            ("안녕", "Korean greeting"),
            ("Hello!", "Greeting with punctuation"),
        ]

        print("\nRunning tests...")
        results = []

        for task_input, description in test_cases:
            print(f"\n  Testing: '{task_input}' ({description})")

            # Create initial state
            state = create_initial_state(
                task_description=task_input,
                task_id=f"test-{task_input}",
                workflow_domain=WorkflowDomain.GENERAL,
                workspace="/tmp/test",
                max_iterations=3,
                recursion_limit=100,
            )

            # Call plan_node directly
            result_state = await workflow.plan_node(state)

            # Check results
            status = result_state.get("task_status", "UNKNOWN")
            should_continue = result_state.get("should_continue", True)
            result_text = result_state.get("task_result", "")

            # Greeting should be detected and completed immediately
            if status == TaskStatus.COMPLETED.value and not should_continue:
                print(f"    ✅ PASS: Detected and completed immediately")
                print(f"       Status: {status}")
                print(f"       Result: {result_text[:80]}...")
                results.append(("PASS", task_input, description))
            else:
                print(f"    ❌ FAIL")
                print(f"       Status: {status}")
                print(f"       should_continue: {should_continue}")
                print(f"       Result: {result_text}")
                results.append(("FAIL", task_input, description))

        # Test non-greeting input (should NOT be detected as greeting)
        print(f"\n  Testing: 'hello world this is a longer sentence' (Not a greeting)")
        state = create_initial_state(
            task_description="hello world this is a longer sentence",
            task_id="test-not-greeting",
            workflow_domain=WorkflowDomain.GENERAL,
            workspace="/tmp/test",
        )
        result_state = await workflow.plan_node(state)
        status = result_state.get("task_status", "UNKNOWN")

        # This should NOT trigger greeting detection (> 20 chars)
        if status != TaskStatus.COMPLETED.value or "Hello! I'm Agentic 2.0" not in result_state.get("task_result", ""):
            print(f"    ✅ PASS: Not detected as greeting (correct)")
            results.append(("PASS", "long-hello", "Long sentence with hello"))
        else:
            print(f"    ❌ FAIL: Incorrectly detected as greeting")
            results.append(("FAIL", "long-hello", "Long sentence with hello"))

        # Summary
        print("\n" + "=" * 80)
        print("Test Summary")
        print("=" * 80)

        passed = sum(1 for r in results if r[0] == "PASS")
        failed = sum(1 for r in results if r[0] == "FAIL")

        print(f"\nTotal: {len(results)} tests")
        print(f"✅ Passed: {passed}/{len(results)}")
        print(f"❌ Failed: {failed}/{len(results)}")

        if failed > 0:
            print("\nFailed tests:")
            for status, task, desc in results:
                if status != "PASS":
                    print(f"  - {task}: {desc}")

        print("\n" + "=" * 80)
        if failed == 0:
            print("✅ ALL TESTS PASSED - Greeting detection working correctly!")
            print("=" * 80)
            return 0
        else:
            print("❌ SOME TESTS FAILED")
            print("=" * 80)
            return 1

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_greeting_detection_direct())
    sys.exit(exit_code)
