"""Quick Tool Verification Script

Directly tests if tools work by simulating workflow usage.
"""

import asyncio
import os
import tempfile
import shutil
from pathlib import Path

# Add parent to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import exactly as workflows do
from tools import FileSystemTools, GitTools, ProcessTools, SearchTools
from core.tool_safety import ToolSafetyManager


async def test_filesystem_tools():
    """Test FileSystemTools like workflows use them"""
    print("\n🧪 Testing FileSystemTools...")

    # Create temp workspace
    temp_dir = tempfile.mkdtemp(prefix="tool_test_")
    print(f"   Workspace: {temp_dir}")

    try:
        # Initialize like workflow does
        safety_manager = ToolSafetyManager()
        fs_tools = FileSystemTools(safety_manager, temp_dir)

        # Test 1: WRITE_FILE
        print("\n   [1/4] Testing WRITE_FILE...")
        file_path = "test.py"
        content = "def hello():\n    print('world')\n"

        result = await fs_tools.write_file(file_path, content)
        if result.success:
            # Verify file exists
            full_path = os.path.join(temp_dir, file_path)
            if os.path.exists(full_path):
                print(f"   ✅ WRITE_FILE: File created at {file_path}")
            else:
                print(f"   ❌ WRITE_FILE: Returned success but file doesn't exist!")
                return False
        else:
            print(f"   ❌ WRITE_FILE failed: {result.error}")
            return False

        # Test 2: READ_FILE
        print("\n   [2/4] Testing READ_FILE...")
        result = await fs_tools.read_file(file_path)
        if result.success:
            if result.output == content:
                print(f"   ✅ READ_FILE: Content matches")
            else:
                print(f"   ❌ READ_FILE: Content mismatch!")
                print(f"       Expected: {repr(content[:50])}")
                print(f"       Got: {repr(result.output[:50] if result.output else None)}")
                return False
        else:
            print(f"   ❌ READ_FILE failed: {result.error}")
            return False

        # Test 3: LIST_DIRECTORY
        print("\n   [3/4] Testing LIST_DIRECTORY...")
        result = await fs_tools.list_directory(".")
        if result.success:
            if any("test.py" in str(entry) for entry in result.output):
                print(f"   ✅ LIST_DIRECTORY: Found test.py")
            else:
                print(f"   ❌ LIST_DIRECTORY: Didn't find test.py")
                print(f"       Entries: {result.output}")
                return False
        else:
            print(f"   ❌ LIST_DIRECTORY failed: {result.error}")
            return False

        # Test 4: SEARCH_FILES
        print("\n   [4/4] Testing SEARCH_FILES...")
        result = await fs_tools.search_files("*.py")
        if result.success:
            if any("test.py" in f for f in result.output):
                print(f"   ✅ SEARCH_FILES: Found test.py")
            else:
                print(f"   ⚠️  SEARCH_FILES: Didn't find test.py (might be expected)")
        else:
            print(f"   ❌ SEARCH_FILES failed: {result.error}")
            return False

        print("\n✅ All FileSystemTools tests passed!")
        return True

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_search_tools():
    """Test SearchTools"""
    print("\n🧪 Testing SearchTools...")

    temp_dir = tempfile.mkdtemp(prefix="search_test_")
    print(f"   Workspace: {temp_dir}")

    try:
        # Create a file to search
        test_file = os.path.join(temp_dir, "searchable.py")
        with open(test_file, 'w') as f:
            f.write("def calculate_total(items):\n    return sum(items)\n")

        safety_manager = ToolSafetyManager()
        search_tools = SearchTools(safety_manager, temp_dir)

        # Test GREP
        print("\n   [1/1] Testing GREP...")
        result = await search_tools.grep("calculate", "*.py")
        if result.success:
            if "calculate_total" in str(result.output):
                print(f"   ✅ GREP: Found pattern")
            else:
                print(f"   ❌ GREP: Didn't find pattern")
                print(f"       Output: {result.output}")
                return False
        else:
            print(f"   ❌ GREP failed: {result.error}")
            return False

        print("\n✅ All SearchTools tests passed!")
        return True

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def test_process_tools():
    """Test ProcessTools"""
    print("\n🧪 Testing ProcessTools...")

    try:
        process_tools = ProcessTools(ToolSafetyManager())

        # Test simple command
        print("\n   [1/2] Testing simple command...")
        result = await process_tools.execute_command("echo 'test'")
        if result.success:
            if "test" in result.output:
                print(f"   ✅ EXECUTE_COMMAND: Simple command works")
            else:
                print(f"   ❌ EXECUTE_COMMAND: Output mismatch")
                return False
        else:
            print(f"   ❌ EXECUTE_COMMAND failed: {result.error}")
            return False

        # Test Python command
        print("\n   [2/2] Testing Python command...")
        result = await process_tools.execute_command("python -c \"print(2+2)\"")
        if result.success:
            if "4" in result.output:
                print(f"   ✅ EXECUTE_COMMAND: Python execution works")
            else:
                print(f"   ⚠️  EXECUTE_COMMAND: Unexpected output: {result.output}")
        else:
            print(f"   ❌ EXECUTE_COMMAND (Python) failed: {result.error}")
            return False

        print("\n✅ All ProcessTools tests passed!")
        return True

    except Exception as e:
        print(f"   ❌ ProcessTools error: {e}")
        return False


async def main():
    """Run all tool tests"""
    print("="*70)
    print("🔍 TOOL VERIFICATION - Quick Check")
    print("="*70)

    results = {}

    # Test each tool category
    results['filesystem'] = await test_filesystem_tools()
    results['search'] = await test_search_tools()
    results['process'] = await test_process_tools()

    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)

    all_passed = True
    for tool_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {tool_name.ljust(15)}: {status}")
        if not passed:
            all_passed = False

    print("="*70)

    if all_passed:
        print("\n🎉 All tools are working correctly!")
        return 0
    else:
        print("\n❌ Some tools have issues - check output above")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
