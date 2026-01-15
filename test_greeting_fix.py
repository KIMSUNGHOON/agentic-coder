#!/usr/bin/env python3
"""Test greeting detection and workflow termination fixes"""
import asyncio
import sys
from pathlib import Path

# Add agentic-ai to path
sys.path.insert(0, str(Path(__file__).parent / "agentic-ai"))

from core.llm_client import DualEndpointLLMClient
from core.tool_safety import ToolSafetyManager
from core.config_loader import Config
from workflows.orchestrator import WorkflowOrchestrator
from core.state import TaskStatus


async def test_greeting_detection():
    """Test that simple greetings are detected and completed immediately"""
    print("=" * 80)
    print("Testing Greeting Detection and Workflow Termination Fixes")
    print("=" * 80)

    try:
        # Load config
        print("\n[1/5] Loading configuration...")
        config_path = Path(__file__).parent / "agentic-ai" / "config" / "config.yaml"
        config = Config.load(str(config_path))
        print(f"✅ Config loaded (recursion_limit: {config.workflows.recursion_limit})")

        # Initialize LLM client (mock mode - don't need actual server for greeting test)
        print("\n[2/5] Initializing LLM client...")
        llm_client = DualEndpointLLMClient(
            primary_endpoint=config.llm.primary_endpoint,
            secondary_endpoint=config.llm.secondary_endpoint,
            model=config.llm.model,
            timeout=config.llm.timeout,
            max_retries=config.llm.max_retries,
            health_check_interval=config.llm.health_check_interval,
        )
        print("✅ LLM client initialized")

        # Initialize safety manager
        print("\n[3/5] Initializing safety manager...")
        safety = ToolSafetyManager.from_config(config.tools.safety)
        print("✅ Safety manager initialized")

        # Initialize orchestrator
        print("\n[4/5] Initializing orchestrator...")
        recursion_limit = config.workflows.recursion_limit
        orchestrator = WorkflowOrchestrator(
            llm_client=llm_client,
            safety_manager=safety,
            workspace=config.workspace.default_path,
            max_iterations=config.workflows.max_iterations,
            recursion_limit=recursion_limit,
        )
        print(f"✅ Orchestrator initialized (recursion_limit: {recursion_limit})")

        # Test greeting inputs
        print("\n[5/5] Testing greeting detection...")
        test_cases = [
            ("hello", "Simple greeting"),
            ("hi", "Short greeting"),
            ("hey there", "Casual greeting"),
            ("안녕", "Korean greeting"),
        ]

        results = []
        for task_input, description in test_cases:
            print(f"\n  Testing: '{task_input}' ({description})")
            try:
                result = await orchestrator.execute_task(
                    task_description=task_input,
                    task_id=f"test-greeting-{task_input}"
                )

                # Check result
                status = result.final_state.get("task_status", "UNKNOWN")
                result_text = result.final_state.get("task_result", "")
                error = result.final_state.get("task_error", "")
                iterations = result.final_state.get("iteration", 0)

                # Greeting should complete in 0 iterations (immediate)
                if status == TaskStatus.COMPLETED.value and iterations == 0:
                    print(f"    ✅ PASS: Completed immediately (0 iterations)")
                    print(f"       Result: {result_text[:80]}...")
                    results.append(("PASS", task_input, description))
                else:
                    print(f"    ❌ FAIL: status={status}, iterations={iterations}")
                    if error:
                        print(f"       Error: {error}")
                    results.append(("FAIL", task_input, description))

            except Exception as e:
                print(f"    ❌ ERROR: {e}")
                results.append(("ERROR", task_input, str(e)))

        # Summary
        print("\n" + "=" * 80)
        print("Test Summary")
        print("=" * 80)

        passed = sum(1 for r in results if r[0] == "PASS")
        failed = sum(1 for r in results if r[0] == "FAIL")
        errors = sum(1 for r in results if r[0] == "ERROR")

        print(f"\nTotal: {len(results)} tests")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Errors: {errors}")

        if failed > 0 or errors > 0:
            print("\nFailed/Error tests:")
            for status, task, desc in results:
                if status != "PASS":
                    print(f"  - {task}: {desc} ({status})")

        # Exit code
        success = (failed == 0 and errors == 0)
        print("\n" + "=" * 80)
        if success:
            print("✅ ALL TESTS PASSED")
        else:
            print("❌ SOME TESTS FAILED")
        print("=" * 80)

        return 0 if success else 1

    except Exception as e:
        print(f"\n❌ Test setup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_greeting_detection())
    sys.exit(exit_code)
