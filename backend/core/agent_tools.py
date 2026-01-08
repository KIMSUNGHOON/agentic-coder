"""Concrete Action Tools for LLM Tool Use Pattern

This module exposes CONCRETE ACTION TOOLS (not abstract agent roles) to the LLM,
following the Claude Code / ChatGPT approach.

OLD APPROACH (Wrong - Hardcoded Agents):
- architect_agent, coder_agent, reviewer_agent, etc.
- Still hardcoding! Just moved from workflow types to agent tools
- LLM can't combine freely - stuck with 8 fixed agents

NEW APPROACH (Correct - Concrete Actions):
- read_file, write_file, execute_python, git_commit, web_search, etc.
- 20+ concrete tools from ToolRegistry
- LLM freely combines these for ANY task
- No hardcoding - true dynamic workflow

Example Usage:
```python
# Get all tools for LLM
tools = get_agent_tools()

# LLM decides: "I need to read config, then search code, then create file"
# - read_file("config.py")
# - code_search("authentication")
# - write_file("auth.py", content)
```

Key Philosophy:
- Tools are ACTIONS, not ROLES
- LLM is the orchestrator, tools are the instruments
- ask_human is for STRATEGIC decisions, not information gathering
"""

from typing import List, Dict, Any
import logging

# Import converter to get concrete tools from registry
from app.tools.tool_converter import (
    get_concrete_tools_from_registry,
    add_strategic_tools
)

logger = logging.getLogger(__name__)


# ============================================
# Tool Retrieval
# ============================================

def get_agent_tools() -> List[Dict[str, Any]]:
    """Get all concrete action tools for LLM Tool Use

    This returns 20+ concrete tools from ToolRegistry plus strategic meta-tools:

    **Concrete Action Tools (from ToolRegistry):**
    - File: read_file, write_file, search_files, list_directory
    - Code: execute_python, run_tests, lint_code, format_code, shell_command, generate_docstring
    - Git: git_status, git_diff, git_log, git_branch, git_commit
    - Web: web_search, http_request, download_file
    - Search: code_search (semantic search with ChromaDB)
    - Sandbox: sandbox_execute (isolated execution)

    **Strategic Meta-Tools:**
    - ask_human: Ask for strategic decisions (architecture choices, dangerous ops)
    - complete_task: Mark task complete and return final response

    Returns:
        List of OpenAI-compatible function definitions
    """
    # Get concrete action tools from registry
    concrete_tools = get_concrete_tools_from_registry()

    # Add strategic meta-tools (ask_human, complete_task)
    all_tools = add_strategic_tools(concrete_tools)

    logger.info(f"🔧 Loaded {len(all_tools)} tools for LLM Tool Use:")
    logger.info(f"   - {len(concrete_tools)} concrete action tools")
    logger.info(f"   - 2 strategic meta-tools (ask_human, complete_task)")

    return all_tools


def get_tool_names() -> List[str]:
    """Get list of all available tool names

    Returns:
        List of tool names (e.g., ['read_file', 'execute_python', ...])
    """
    tools = get_agent_tools()
    return [tool["function"]["name"] for tool in tools]


def get_tool_by_name(name: str) -> Dict[str, Any]:
    """Get tool definition by name

    Args:
        name: Tool name (e.g., 'read_file')

    Returns:
        OpenAI-compatible function definition

    Raises:
        ValueError: If tool not found
    """
    tools = get_agent_tools()
    for tool in tools:
        if tool["function"]["name"] == name:
            return tool
    raise ValueError(f"Tool '{name}' not found. Available: {get_tool_names()}")


def get_tool_categories() -> Dict[str, List[str]]:
    """Get tools organized by category

    Returns:
        Dictionary mapping category to list of tool names
        Example: {'file': ['read_file', 'write_file'], 'code': [...]}
    """
    from app.tools.registry import get_registry

    registry = get_registry()
    categories = {}

    for tool in registry.list_tools():
        category = tool.category.value
        if category not in categories:
            categories[category] = []
        categories[category].append(tool.name)

    # Add strategic tools
    categories["meta"] = ["ask_human", "complete_task"]

    return categories


# ============================================
# Tool Statistics
# ============================================

def get_tool_statistics() -> Dict[str, Any]:
    """Get comprehensive tool statistics

    Returns:
        Dictionary with tool counts, categories, network modes, etc.
    """
    from app.tools.registry import get_registry

    registry = get_registry()
    stats = registry.get_statistics()

    # Add strategic tool info
    stats["strategic_tools"] = 2
    stats["total_tools_with_meta"] = stats["total_tools"] + 2

    return stats


# ============================================
# Tool Documentation
# ============================================

def print_tool_documentation():
    """Print human-readable tool documentation

    Useful for debugging and understanding available tools
    """
    categories = get_tool_categories()

    print("\n" + "="*80)
    print("AVAILABLE TOOLS FOR LLM TOOL USE")
    print("="*80)

    for category, tool_names in sorted(categories.items()):
        print(f"\n## {category.upper()} ({len(tool_names)} tools)")
        for name in sorted(tool_names):
            print(f"   - {name}")

    stats = get_tool_statistics()
    print(f"\n{'='*80}")
    print(f"TOTAL: {stats['total_tools_with_meta']} tools")
    print(f"  - Concrete action tools: {stats['total_tools']}")
    print(f"  - Strategic meta-tools: {stats['strategic_tools']}")
    print(f"  - Network mode: {stats['network_mode']}")
    print(f"  - Available in current mode: {stats['available_tools']}")
    if stats['disabled_tools'] > 0:
        print(f"  - Disabled (offline mode): {stats['disabled_tools']}")
    print("="*80 + "\n")


# ============================================
# Legacy Compatibility (for migration period)
# ============================================

# For code that still references old agent names during migration
LEGACY_AGENT_MAPPING = {
    "architect_agent": ["read_file", "search_files", "list_directory"],
    "coder_agent": ["write_file", "execute_python", "format_code"],
    "reviewer_agent": ["read_file", "lint_code"],
    "refiner_agent": ["read_file", "write_file", "format_code"],
    "qa_tester_agent": ["execute_python", "run_tests"],
    "security_auditor_agent": ["read_file", "lint_code", "code_search"],
}


def get_tools_for_legacy_agent(agent_name: str) -> List[str]:
    """Get recommended concrete tools for legacy agent names

    This is for backward compatibility during migration.

    Args:
        agent_name: Legacy agent name (e.g., 'coder_agent')

    Returns:
        List of recommended concrete tool names

    Example:
        get_tools_for_legacy_agent('coder_agent')
        # Returns: ['write_file', 'execute_python', 'format_code']
    """
    return LEGACY_AGENT_MAPPING.get(agent_name, [])


# ============================================
# Module Initialization
# ============================================

# Log tool loading on import
logger.info("🔧 agent_tools.py loaded - using CONCRETE ACTION TOOLS")
logger.info(f"   Available tools: {len(get_tool_names())}")
logger.info("   Mode: Dynamic LLM-driven Tool Use (no hardcoding)")
