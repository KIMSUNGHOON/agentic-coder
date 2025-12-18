"""Real file system tools for LangGraph agents

These tools perform ACTUAL file operations, not simulations.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ReadFileInput(BaseModel):
    """Input for read_file tool"""
    file_path: str = Field(description="Path to file to read")
    workspace_root: str = Field(description="Workspace root directory")


class WriteFileInput(BaseModel):
    """Input for write_file tool"""
    file_path: str = Field(description="Path to file to write")
    content: str = Field(description="Content to write to file")
    workspace_root: str = Field(description="Workspace root directory")


class ListFilesInput(BaseModel):
    """Input for list_files tool"""
    directory: str = Field(description="Directory to list files from")
    workspace_root: str = Field(description="Workspace root directory")
    pattern: str = Field(default="*", description="File pattern to match")


def read_file_tool(file_path: str, workspace_root: str) -> Dict:
    """Read a file from the workspace

    CRITICAL: This is a REAL file operation, not a simulation.

    Args:
        file_path: Path to file (relative or absolute)
        workspace_root: Workspace root directory

    Returns:
        Dict with file content or error
    """
    try:
        # Validate path is within workspace
        from app.agent.langgraph.tools.file_validator import FileValidator

        validator = FileValidator(workspace_root)
        is_valid, error, resolved_path = validator.validate_path(file_path)

        if not is_valid:
            logger.error(f"❌ Path validation failed: {error}")
            return {
                "success": False,
                "error": error,
                "content": None
            }

        # Read file
        if not resolved_path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "content": None
            }

        content = resolved_path.read_text(encoding='utf-8')
        logger.info(f"✅ Read file: {file_path} ({len(content)} bytes)")

        return {
            "success": True,
            "error": None,
            "content": content,
            "size": len(content)
        }

    except Exception as e:
        logger.error(f"❌ Error reading file {file_path}: {e}")
        return {
            "success": False,
            "error": str(e),
            "content": None
        }


def write_file_tool(file_path: str, content: str, workspace_root: str) -> Dict:
    """Write content to a file in the workspace

    CRITICAL: This is a REAL file operation that writes to disk.

    Args:
        file_path: Path to file (relative or absolute)
        content: Content to write
        workspace_root: Workspace root directory

    Returns:
        Dict with success status
    """
    try:
        # Validate path is within workspace
        from app.agent.langgraph.tools.file_validator import FileValidator

        validator = FileValidator(workspace_root)
        is_valid, error, resolved_path = validator.validate_path(file_path)

        if not is_valid:
            logger.error(f"❌ Path validation failed: {error}")
            return {
                "success": False,
                "error": error,
                "file_path": file_path
            }

        # Create parent directories if needed
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        resolved_path.write_text(content, encoding='utf-8')
        logger.info(f"✅ Wrote file: {file_path} ({len(content)} bytes)")

        return {
            "success": True,
            "error": None,
            "file_path": str(resolved_path),
            "size": len(content)
        }

    except Exception as e:
        logger.error(f"❌ Error writing file {file_path}: {e}")
        return {
            "success": False,
            "error": str(e),
            "file_path": file_path
        }


def list_files_tool(directory: str, workspace_root: str, pattern: str = "*") -> Dict:
    """List files in a directory

    Args:
        directory: Directory to list
        workspace_root: Workspace root directory
        pattern: Glob pattern to match

    Returns:
        Dict with list of files
    """
    try:
        # Validate path is within workspace
        from app.agent.langgraph.tools.file_validator import FileValidator

        validator = FileValidator(workspace_root)
        is_valid, error, resolved_path = validator.validate_path(directory)

        if not is_valid:
            logger.error(f"❌ Path validation failed: {error}")
            return {
                "success": False,
                "error": error,
                "files": []
            }

        if not resolved_path.exists():
            return {
                "success": False,
                "error": f"Directory not found: {directory}",
                "files": []
            }

        if not resolved_path.is_dir():
            return {
                "success": False,
                "error": f"Not a directory: {directory}",
                "files": []
            }

        # List files
        files = []
        for file_path in resolved_path.glob(pattern):
            if file_path.is_file():
                files.append({
                    "name": file_path.name,
                    "path": str(file_path.relative_to(workspace_root)),
                    "size": file_path.stat().st_size
                })

        logger.info(f"✅ Listed {len(files)} files in {directory}")

        return {
            "success": True,
            "error": None,
            "files": files,
            "count": len(files)
        }

    except Exception as e:
        logger.error(f"❌ Error listing directory {directory}: {e}")
        return {
            "success": False,
            "error": str(e),
            "files": []
        }


# Create LangChain StructuredTools
read_file = StructuredTool.from_function(
    func=read_file_tool,
    name="read_file",
    description="Read a file from the workspace. Returns file content.",
    args_schema=ReadFileInput
)

write_file = StructuredTool.from_function(
    func=write_file_tool,
    name="write_file",
    description="Write content to a file in the workspace. CREATES REAL FILES.",
    args_schema=WriteFileInput
)

list_files = StructuredTool.from_function(
    func=list_files_tool,
    name="list_files",
    description="List files in a directory matching a pattern.",
    args_schema=ListFilesInput
)


# Tool registry
FILESYSTEM_TOOLS = [read_file, write_file, list_files]
