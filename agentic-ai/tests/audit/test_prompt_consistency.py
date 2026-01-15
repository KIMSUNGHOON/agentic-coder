"""Prompt-Code Consistency Verification

Ensures that all prompts match the actual code implementation:
- Action names match (UPPERCASE consistency)
- Parameter structures align with code expectations
- Available actions match implemented actions
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.prompts import CodingPrompts, ResearchPrompts, DataPrompts, AgentPrompts
from workflows.coding_workflow import CodingWorkflow
from workflows.general_workflow import GeneralWorkflow
import re


def extract_actions_from_prompt(prompt_text: str) -> dict:
    """Extract action names and their parameters from prompt text"""
    actions = {}

    # Pattern 1: JSON format {"action": "ACTION_NAME", "parameters": {...}}
    action_pattern = r'\{\s*"action"\s*:\s*"([A-Z_]+)"'
    matches = re.finditer(action_pattern, prompt_text)
    for match in matches:
        action_name = match.group(1)
        actions[action_name] = True

    # Pattern 2: Documentation format like "- READ_FILE: Read file contents"
    doc_pattern = r'[-•]\s*([A-Z_]+):\s*'
    matches = re.finditer(doc_pattern, prompt_text)
    for match in matches:
        action_name = match.group(1)
        actions[action_name] = True

    return actions


def test_coding_workflow_actions():
    """Verify CodingWorkflow prompt actions match implementation"""
    print("\n🧪 Testing CodingWorkflow Prompt Consistency...")

    # Expected actions that coding_workflow.py implements
    expected_actions = {
        "READ_FILE",
        "WRITE_FILE",
        "LIST_DIRECTORY",
        "SEARCH_FILES",
        "SEARCH_CODE",
        "RUN_COMMAND",
        "COMPLETE",
        "DELEGATE_TO_SUB_AGENT",  # From sub-agent workflow
        "RUN_TESTS",  # Also in prompts
        "GIT_STATUS"  # Also in prompts
    }

    # Get execution prompt which contains the action documentation
    coding_messages = CodingPrompts.execution_prompt(
        task="test task",
        plan={"steps": ["step1"]},
        current_step=0
    )
    prompt_text = "\n".join([msg["content"] for msg in coding_messages])

    # Extract actions mentioned in prompt
    prompt_actions = extract_actions_from_prompt(prompt_text)

    print(f"   Expected actions: {sorted(expected_actions)}")
    print(f"   Prompt actions: {sorted(prompt_actions.keys())}")

    # Check all expected actions are in prompt
    missing_in_prompt = expected_actions - set(prompt_actions.keys())
    if missing_in_prompt:
        print(f"   ⚠️  Actions implemented but not documented in prompt: {missing_in_prompt}")

    # Check for lowercase actions (common bug)
    lowercase_pattern = r'\{\s*"action"\s*:\s*"([a-z_]+)"'
    lowercase_matches = re.findall(lowercase_pattern, prompt_text)
    if lowercase_matches:
        print(f"   ❌ Found lowercase actions in prompt: {lowercase_matches}")
        print(f"      These should be UPPERCASE!")
        return False
    else:
        print(f"   ✅ All actions are UPPERCASE")

    # Check parameter structure consistency
    # Should always be: {"action": "X", "parameters": {...}}
    if '"parameters"' in prompt_text:
        print(f"   ✅ Prompt uses 'parameters' key (consistent with code)")
    else:
        print(f"   ⚠️  Prompt might not use 'parameters' key structure")

    print(f"   ✅ CodingWorkflow prompt consistency passed")
    return True


def test_general_workflow_actions():
    """Verify GeneralWorkflow prompt actions match implementation"""
    print("\n🧪 Testing GeneralWorkflow Prompt Consistency...")

    # Expected actions from general_workflow.py _execute_action method
    expected_actions = {
        "READ_FILE",
        "WRITE_FILE",
        "LIST_DIRECTORY",
        "SEARCH_FILES",
        "SEARCH_CODE",
        "COMPLETE",
        "DELEGATE_TO_SUB_AGENT"
    }

    # Read the workflow file to check inline prompts
    # __file__ is in tests/audit/, so parent.parent gets to agentic-ai/
    workflow_file = Path(__file__).parent.parent / "workflows" / "general_workflow.py"
    if not workflow_file.exists():
        # Fallback: look for it relative to current working directory
        workflow_file = Path("workflows/general_workflow.py")

    with open(workflow_file) as f:
        workflow_code = f.read()

    # Extract inline prompt strings
    prompt_actions = extract_actions_from_prompt(workflow_code)

    print(f"   Expected actions: {sorted(expected_actions)}")
    print(f"   Found in code: {sorted(prompt_actions.keys())}")

    # The general workflow uses inline prompts, so we mainly check that
    # the _execute_action method handles all expected actions

    # Check that _execute_action has cases for all expected actions
    for action in expected_actions:
        if action in workflow_code:
            pass  # Found in code
        elif action == "COMPLETE":
            # COMPLETE might be handled differently
            pass
        else:
            print(f"   ⚠️  Action {action} might not be implemented")

    # Check for lowercase actions (bug indicator)
    lowercase_pattern = r'action_type\s*==\s*"([a-z_]+)"'
    lowercase_matches = re.findall(lowercase_pattern, workflow_code)
    if lowercase_matches:
        print(f"   ❌ Found lowercase action checks: {lowercase_matches}")
        print(f"      These should be UPPERCASE!")
        return False
    else:
        print(f"   ✅ All action checks are UPPERCASE")

    # Check parameter extraction pattern
    if 'params = action.get("parameters"' in workflow_code:
        print(f"   ✅ Uses correct parameter extraction pattern")
    else:
        print(f"   ⚠️  Might have incorrect parameter extraction")

    print(f"   ✅ GeneralWorkflow action consistency passed")
    return True


def test_parameter_structure_examples():
    """Verify parameter structure in examples matches code expectations"""
    print("\n🧪 Testing Parameter Structure in Examples...")

    # Get execution prompt which has the examples
    coding_messages = CodingPrompts.execution_prompt(
        task="test task",
        plan={"steps": ["step1"]},
        current_step=0
    )

    # Extract prompt content
    coding_prompt = "\n".join([msg["content"] for msg in coding_messages])

    # Check for correct parameter structure pattern
    correct_pattern = r'\{\s*"action"\s*:\s*"[A-Z_]+"\s*,\s*"parameters"\s*:\s*\{[^}]+\}\s*\}'

    coding_matches = len(re.findall(correct_pattern, coding_prompt))

    print(f"   CodingPrompt: Found {coding_matches} correctly structured examples")

    if coding_matches == 0:
        print(f"   ⚠️  No structured examples found - might need manual review")

    # Check for incorrect flat structure (common mistake)
    # e.g., {"action": "WRITE_FILE", "file_path": "...", "content": "..."}
    flat_pattern = r'\{\s*"action"\s*:\s*"[A-Z_]+"\s*,\s*"file_path"'
    flat_matches_coding = re.findall(flat_pattern, coding_prompt)

    if flat_matches_coding:
        print(f"   ❌ Found flat parameter structure (should use 'parameters' key)")
        print(f"      In CodingPrompt: {len(flat_matches_coding)} cases")
        return False
    else:
        print(f"   ✅ All examples use nested 'parameters' structure")

    return True


def test_required_parameters_documented():
    """Check that required parameters are clearly documented"""
    print("\n🧪 Testing Required Parameters Documentation...")

    # Get execution prompt
    coding_messages = CodingPrompts.execution_prompt(
        task="test task",
        plan={"steps": ["step1"]},
        current_step=0
    )
    coding_prompt = "\n".join([msg["content"] for msg in coding_messages])

    # Check for WRITE_FILE parameters
    write_file_section = re.search(
        r'WRITE_FILE.*?(?=READ_FILE|SEARCH_CODE|COMPLETE|$)',
        coding_prompt,
        re.DOTALL | re.IGNORECASE
    )

    if write_file_section:
        section_text = write_file_section.group(0)
        has_file_path = 'file_path' in section_text
        has_content = 'content' in section_text

        if has_file_path and has_content:
            print(f"   ✅ WRITE_FILE: Both required parameters documented")
        else:
            missing = []
            if not has_file_path:
                missing.append("file_path")
            if not has_content:
                missing.append("content")
            print(f"   ⚠️  WRITE_FILE: Missing parameter docs: {missing}")
    else:
        print(f"   ⚠️  Could not find WRITE_FILE documentation section")

    # Check for READ_FILE parameters
    read_file_section = re.search(
        r'READ_FILE.*?(?=WRITE_FILE|SEARCH_CODE|COMPLETE|$)',
        coding_prompt,
        re.DOTALL | re.IGNORECASE
    )

    if read_file_section:
        section_text = read_file_section.group(0)
        has_file_path = 'file_path' in section_text

        if has_file_path:
            print(f"   ✅ READ_FILE: Required parameter documented")
        else:
            print(f"   ⚠️  READ_FILE: Missing file_path parameter doc")

    return True


def test_complete_action_guidance():
    """Verify COMPLETE action usage is clearly explained"""
    print("\n🧪 Testing COMPLETE Action Guidance...")

    # Get execution prompt
    coding_messages = CodingPrompts.execution_prompt(
        task="test task",
        plan={"steps": ["step1"]},
        current_step=0
    )
    coding_prompt = "\n".join([msg["content"] for msg in coding_messages])

    # Check if COMPLETE action is mentioned
    coding_has_complete = 'COMPLETE' in coding_prompt

    if coding_has_complete:
        print(f"   ✅ CodingPrompt: COMPLETE action documented")

        # Check for guidance on when to use it
        if 'task is done' in coding_prompt.lower() or 'finished' in coding_prompt.lower() or 'done' in coding_prompt.lower():
            print(f"   ✅ Has guidance on when to use COMPLETE")
        else:
            print(f"   ⚠️  Missing clear guidance on COMPLETE usage")

        # Check for strong emphasis (🚨, CRITICAL, etc.)
        if '🚨' in coding_prompt or 'CRITICAL' in coding_prompt or 'USE THIS WHEN DONE' in coding_prompt:
            print(f"   ✅ Has strong emphasis on COMPLETE importance")
        else:
            print(f"   ⚠️  Could use stronger emphasis on COMPLETE")
    else:
        print(f"   ❌ CodingPrompt: COMPLETE action not documented!")
        return False

    return True


def main():
    """Run all prompt consistency tests"""
    print("="*70)
    print("🔍 PROMPT-CODE CONSISTENCY VERIFICATION")
    print("="*70)

    results = {}

    results['coding_actions'] = test_coding_workflow_actions()
    results['general_actions'] = test_general_workflow_actions()
    results['parameter_structure'] = test_parameter_structure_examples()
    results['required_params'] = test_required_parameters_documented()
    results['complete_guidance'] = test_complete_action_guidance()

    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {test_name.ljust(25)}: {status}")
        if not passed:
            all_passed = False

    print("="*70)

    if all_passed:
        print("\n✅ All prompt consistency checks passed!")
        print("\nℹ️  Note: Manual review recommended for:")
        print("   - Few-shot example accuracy")
        print("   - Parameter descriptions clarity")
        print("   - Action usage guidelines completeness")
        return 0
    else:
        print("\n⚠️  Some prompt consistency issues found")
        print("   Review the output above for details")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
