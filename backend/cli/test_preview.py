"""Test /preview command functionality"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest

# Check for required CLI dependencies
try:
    import rich
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Skip entire module if rich is not available
if not RICH_AVAILABLE:
    pytest.skip(
        "CLI tests require 'rich' package: pip install rich",
        allow_module_level=True
    )

from cli.terminal_ui import TerminalUI
from cli.session_manager import SessionManager


def test_preview():
    """Test the /preview command"""
    print("Testing /preview command...")
    print("=" * 60)

    # Create session manager and UI
    session_mgr = SessionManager(
        workspace="/home/user/TestCodeAgent",
        auto_save=False
    )

    ui = TerminalUI(session_mgr)

    # Test /preview command
    print("\n[Test 1] Preview test_calculator.py")
    print("-" * 60)
    ui._cmd_preview(["test_calculator.py"])

    print("\n\n[Test 2] Preview non-existent file")
    print("-" * 60)
    ui._cmd_preview(["non_existent_file.py"])

    print("\n\n[Test 3] Preview without arguments")
    print("-" * 60)
    ui._cmd_preview([])

    print("\n\n[Test 4] Preview with path that has spaces")
    print("-" * 60)
    # This should fail but test the path joining logic
    ui._cmd_preview(["test", "calculator.py"])

    print("\n" + "=" * 60)
    print("✅ /preview command tests completed!")


if __name__ == "__main__":
    test_preview()
