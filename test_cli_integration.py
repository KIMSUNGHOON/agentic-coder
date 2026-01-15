#!/usr/bin/env python3
"""Test CLI Integration

Simple test script to verify CLI backend integration works correctly.
"""

import asyncio
import sys
from pathlib import Path

# Add agentic-ai to path
sys.path.insert(0, str(Path(__file__).parent / "agentic-ai"))


async def test_backend_initialization():
    """Test backend bridge initialization"""
    print("🧪 Test 1: Backend Initialization")
    print("-" * 50)

    try:
        from cli.backend_bridge import BackendBridge

        bridge = BackendBridge()
        print("✅ BackendBridge created")

        await bridge.initialize()
        print("✅ Backend initialized successfully")

        # Check health
        health = await bridge.get_health_status()
        print(f"✅ Health status: {health['status']}")
        print(f"   LLM endpoints: {health['llm']['healthy_endpoints']}/{health['llm']['total_endpoints']}")
        print(f"   Orchestrator ready: {health['orchestrator']['total_tasks']} tasks processed")

        # Clean up
        await bridge.close()
        print("✅ Backend closed")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_simple_task():
    """Test simple task execution"""
    print("\n🧪 Test 2: Simple Task Execution")
    print("-" * 50)

    try:
        from cli.backend_bridge import get_bridge

        bridge = get_bridge()

        # Execute a simple task
        task = "What is 2 + 2?"
        print(f"📋 Task: {task}")
        print()

        async for update in bridge.execute_task(task):
            if update.type == "status":
                print(f"   📊 {update.message}")

            elif update.type == "cot":
                print(f"   🤔 CoT (step {update.data.get('step', 0)}): {update.message[:80]}...")

            elif update.type == "result":
                if update.data["success"]:
                    print(f"\n✅ Task completed!")
                    print(f"   Output: {update.data.get('output')}")
                else:
                    print(f"\n❌ Task failed: {update.data.get('error')}")

        # Clean up
        await bridge.close()

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_cot_parsing():
    """Test Chain-of-Thought parsing"""
    print("\n🧪 Test 3: Chain-of-Thought Parsing")
    print("-" * 50)

    try:
        from cli.backend_bridge import BackendBridge
        from workflows.base_workflow import WorkflowResult

        bridge = BackendBridge()

        # Test CoT extraction
        test_output = """
        Here is my response.

        <think>
        First, I need to analyze the problem.
        This requires careful consideration.
        </think>

        The answer is 42.

        <think>
        Let me verify this is correct.
        Yes, 42 is the right answer.
        </think>
        """

        result = WorkflowResult(
            success=True,
            output=test_output,
            iterations=1,
            metadata={}
        )

        cot_blocks = bridge._extract_cot_blocks(result)

        print(f"   Found {len(cot_blocks)} CoT blocks")

        for block in cot_blocks:
            print(f"   📝 Step {block.step}: {block.content[:80]}...")

        if len(cot_blocks) == 2:
            print("✅ CoT parsing works correctly")
            return True
        else:
            print(f"❌ Expected 2 blocks, got {len(cot_blocks)}")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("=" * 50)
    print("Agentic 2.0 CLI Integration Tests")
    print("=" * 50)
    print()

    results = []

    # Test 1: Backend initialization
    results.append(await test_backend_initialization())

    # Test 2: Simple task (may fail if vLLM not running)
    # results.append(await test_simple_task())

    # Test 3: CoT parsing
    results.append(await test_cot_parsing())

    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)

    passed = sum(results)
    total = len(results)

    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
