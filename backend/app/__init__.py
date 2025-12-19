"""Coding Agent application.

Sets up Python path for project-wide imports.
"""
import sys
from pathlib import Path

# Add project root to path for shared module access
# backend/app/__init__.py -> backend/app -> backend -> project_root
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Add backend to path for core module access
BACKEND_ROOT = Path(__file__).parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
