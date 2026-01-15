"""Git Tools Quick Check"""

import asyncio
import os
import tempfile
import shutil
import subprocess
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import GitTools
from core.tool_safety import ToolSafetyManager


async def test_git_tools():
    """Test GitTools"""
    print("\n🧪 Testing GitTools...")

    # Create temp git repo
    temp_dir = tempfile.mkdtemp(prefix="git_test_")
    print(f"   Workspace: {temp_dir}")

    try:
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=temp_dir, check=True, capture_output=True)

        # Create a file
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")

        safety_manager = ToolSafetyManager()
        git_tools = GitTools(safety_manager)

        # Git tools work in current directory, so change to temp dir
        original_cwd = os.getcwd()
        os.chdir(temp_dir)

        # Test GIT_STATUS
        print("\n   [1/1] Testing GIT_STATUS...")
        result = await git_tools.status()

        # Restore original directory
        os.chdir(original_cwd)
        if result.success:
            # Should show untracked file
            if "test.txt" in str(result.output) or "Untracked" in str(result.output):
                print(f"   ✅ GIT_STATUS: Detected untracked file")
            else:
                print(f"   ⚠️  GIT_STATUS: Output doesn't show untracked file")
                print(f"       Output: {result.output}")
        else:
            print(f"   ❌ GIT_STATUS failed: {result.error}")
            return False

        print("\n✅ GitTools test passed!")
        return True

    except Exception as e:
        print(f"   ❌ GitTools error: {e}")
        return False

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def main():
    result = await test_git_tools()
    return 0 if result else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
