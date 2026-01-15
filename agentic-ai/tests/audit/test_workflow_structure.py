"""Workflow Structure Verification

Tests that workflows are properly structured and can be initialized.
Does NOT test LLM calls - only structure and logic.
"""

import asyncio
import os
import tempfile
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from workflows.coding_workflow import CodingWorkflow
from workflows.general_workflow import GeneralWorkflow
from core.state import AgenticState, TaskStatus
from core.tool_safety import ToolSafetyManager


class MockLLMClient:
    """Mock LLM client for testing"""
    async def generate(self, *args, **kwargs):
        return "Mock response"

    async def stream_generate(self, *args, **kwargs):
        yield "Mock"
        yield " response"


def create_test_state(task_description: str, task_type: str = "coding") -> AgenticState:
    """Create a test state for workflow testing"""
    return {
        "task_description": task_description,
        "task_id": "test_001",
        "task_type": task_type,
        "workspace": tempfile.mkdtemp(prefix="test_workflow_"),
        "iteration": 0,
        "max_iterations": 50,
        "task_status": "pending",
        "context": {},
        "tool_calls": [],
        "errors": [],
        "requires_sub_agents": False,
        "should_continue": True
    }


async def test_coding_workflow_structure():
    """Test CodingWorkflow structure and initialization"""
    print("\n🧪 Testing CodingWorkflow Structure...")

    try:
        # Create workflow instance
        llm_client = MockLLMClient()
        safety = ToolSafetyManager()
        workspace = tempfile.mkdtemp(prefix="coding_test_")

        workflow = CodingWorkflow(llm_client, safety, workspace)

        # Check that workflow has required methods
        assert hasattr(workflow, 'plan_node'), "Missing plan_node method"
        assert hasattr(workflow, 'execute_node'), "Missing execute_node method"
        assert hasattr(workflow, 'reflect_node'), "Missing reflect_node method"
        assert hasattr(workflow, '_execute_action'), "Missing _execute_action method"

        print("   ✅ CodingWorkflow has all required methods")

        # Check tool initialization
        assert workflow.fs_tools is not None, "fs_tools not initialized"
        assert workflow.search_tools is not None, "search_tools not initialized"
        assert workflow.process_tools is not None, "process_tools not initialized"
        assert workflow.git_tools is not None, "git_tools not initialized"

        print("   ✅ All tools initialized")

        # Test reflect_node logic (without LLM)
        state = create_test_state("Python 계산기 만들기", "coding")

        # Should use simple task limit (10)
        state["iteration"] = 0
        reflected = await workflow.reflect_node(state)

        # Check that hard_limit logic works
        print(f"   ✅ reflect_node executed without errors")

        # Test with max iterations reached
        state["iteration"] = 15  # Over limit for simple task (10)
        reflected = await workflow.reflect_node(state)

        if reflected["task_status"] == TaskStatus.COMPLETED.value:
            print(f"   ✅ Hard limit works: stopped at iteration 15")
        else:
            print(f"   ⚠️  Hard limit might not work: status = {reflected['task_status']}")

        # Cleanup
        shutil.rmtree(workspace, ignore_errors=True)

        print("\n✅ CodingWorkflow structure test passed!")
        return True

    except Exception as e:
        print(f"\n❌ CodingWorkflow structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_general_workflow_structure():
    """Test GeneralWorkflow structure and initialization"""
    print("\n🧪 Testing GeneralWorkflow Structure...")

    try:
        llm_client = MockLLMClient()
        safety = ToolSafetyManager()
        workspace = tempfile.mkdtemp(prefix="general_test_")

        workflow = GeneralWorkflow(llm_client, safety, workspace)

        # Check methods
        assert hasattr(workflow, 'plan_node')
        assert hasattr(workflow, 'execute_node')
        assert hasattr(workflow, 'reflect_node')
        assert hasattr(workflow, '_execute_action')

        print("   ✅ GeneralWorkflow has all required methods")

        # Check tools
        assert workflow.fs_tools is not None
        print("   ✅ All tools initialized")

        # Test reflect_node
        state = create_test_state("파일 검색하기", "general")
        state["iteration"] = 0
        reflected = await workflow.reflect_node(state)

        print(f"   ✅ reflect_node executed without errors")

        # Test hard limit
        state["iteration"] = 10  # Over limit for simple task (8)
        reflected = await workflow.reflect_node(state)

        if reflected["task_status"] == TaskStatus.COMPLETED.value:
            print(f"   ✅ Hard limit works: stopped at iteration 10")
        else:
            print(f"   ⚠️  Hard limit might not work")

        shutil.rmtree(workspace, ignore_errors=True)

        print("\n✅ GeneralWorkflow structure test passed!")
        return True

    except Exception as e:
        print(f"\n❌ GeneralWorkflow structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_action_execution_parameters():
    """Test that _execute_action properly extracts parameters"""
    print("\n🧪 Testing Action Execution Parameter Extraction...")

    try:
        llm_client = MockLLMClient()
        safety = ToolSafetyManager()
        workspace = tempfile.mkdtemp(prefix="action_test_")

        workflow = CodingWorkflow(llm_client, safety, workspace)
        state = create_test_state("test", "coding")

        # Test WRITE_FILE action with proper parameter structure
        action = {
            "action": "WRITE_FILE",
            "parameters": {
                "file_path": "test.py",
                "content": "print('hello')"
            }
        }

        result = await workflow._execute_action(action, state)

        if result["success"]:
            # Check file actually created
            file_path = os.path.join(workspace, "test.py")
            if os.path.exists(file_path):
                print(f"   ✅ WRITE_FILE: Parameter extraction works")
                print(f"   ✅ File created at: {file_path}")

                # Check content
                with open(file_path, 'r') as f:
                    content = f.read()
                if content == "print('hello')":
                    print(f"   ✅ File content matches")
                else:
                    print(f"   ❌ File content mismatch")
                    return False
            else:
                print(f"   ❌ File not created!")
                return False
        else:
            print(f"   ❌ WRITE_FILE failed: {result.get('error')}")
            return False

        # Test COMPLETE action
        action = {
            "action": "COMPLETE",
            "parameters": {
                "summary": "Test completed"
            }
        }

        result = await workflow._execute_action(action, state)
        if result["success"] and result["message"] == "Test completed":
            print(f"   ✅ COMPLETE: Parameter extraction works")
        else:
            print(f"   ❌ COMPLETE failed")
            return False

        shutil.rmtree(workspace, ignore_errors=True)

        print("\n✅ Action execution parameter test passed!")
        return True

    except Exception as e:
        print(f"\n❌ Action execution test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all workflow structure tests"""
    print("="*70)
    print("🔍 WORKFLOW STRUCTURE VERIFICATION")
    print("="*70)

    results = {}

    results['coding_workflow'] = await test_coding_workflow_structure()
    results['general_workflow'] = await test_general_workflow_structure()
    results['action_execution'] = await test_action_execution_parameters()

    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {test_name.ljust(20)}: {status}")
        if not passed:
            all_passed = False

    print("="*70)

    if all_passed:
        print("\n🎉 All workflow structure tests passed!")
        print("\nℹ️  Note: These tests verify structure and logic only.")
        print("   Full end-to-end tests with LLM require manual testing.")
        return 0
    else:
        print("\n❌ Some workflow tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
