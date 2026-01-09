"""Tool Schema Converter - Convert ToolRegistry tools to OpenAI function calling format

This module provides utilities to convert our internal tool schemas
to OpenAI-compatible function calling format for LLM Tool Use.

Internal Format (BaseTool.get_schema()):
{
    "name": "tool_name",
    "category": "file",
    "description": "Tool description",
    "parameters": {
        "param1": {
            "type": "string",
            "required": True,
            "description": "Parameter description",
            "default": "value"
        }
    }
}

OpenAI Format:
{
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "Tool description",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "Parameter description"
                }
            },
            "required": ["param1"]
        }
    }
}
"""

from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


def convert_tool_to_openai_format(tool_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Convert internal tool schema to OpenAI function calling format

    Args:
        tool_schema: Internal tool schema from BaseTool.get_schema()

    Returns:
        OpenAI-compatible function definition
    """
    # Extract required fields
    name = tool_schema.get("name", "unknown")
    description = tool_schema.get("description", "")
    internal_params = tool_schema.get("parameters", {})

    # Check if parameters are already in OpenAI format
    # OpenAI format has "type": "object" and "properties" keys
    if isinstance(internal_params, dict) and internal_params.get("type") == "object" and "properties" in internal_params:
        # Already in OpenAI format, just wrap it
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": internal_params
            }
        }

    # Convert from internal format to OpenAI format
    properties = {}
    required_params = []

    for param_name, param_def in internal_params.items():
        # Skip if param_def is not a dict (defensive programming)
        if not isinstance(param_def, dict):
            logger.warning(f"Skipping parameter '{param_name}' in tool '{name}': not a dict")
            continue

        # Build property definition
        prop = {
            "type": param_def.get("type", "string"),
            "description": param_def.get("description", "")
        }

        # Add enum if present
        if "enum" in param_def:
            prop["enum"] = param_def["enum"]

        # Add default if present
        if "default" in param_def:
            prop["default"] = param_def["default"]

        # Add items for array type
        if param_def.get("type") == "array" and "items" in param_def:
            prop["items"] = param_def["items"]

        properties[param_name] = prop

        # Track required parameters
        if param_def.get("required", False):
            required_params.append(param_name)

    # Build OpenAI format
    openai_schema = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required_params
            }
        }
    }

    return openai_schema


def convert_tools_to_openai_format(tool_schemas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert multiple tool schemas to OpenAI format

    Args:
        tool_schemas: List of internal tool schemas

    Returns:
        List of OpenAI-compatible function definitions
    """
    openai_tools = []

    for schema in tool_schemas:
        try:
            openai_tool = convert_tool_to_openai_format(schema)
            openai_tools.append(openai_tool)
        except Exception as e:
            logger.error(f"Failed to convert tool '{schema.get('name', 'unknown')}': {e}")

    return openai_tools


def get_concrete_tools_from_registry() -> List[Dict[str, Any]]:
    """Get all concrete action tools from ToolRegistry in OpenAI format

    This replaces the old abstract agent tools (architect_agent, coder_agent, etc.)
    with concrete action tools (read_file, execute_python, git_commit, etc.)

    Returns:
        List of OpenAI-compatible function definitions for all registered tools
    """
    from .registry import get_registry

    # Get registry
    registry = get_registry()

    # Get all tool schemas
    internal_schemas = registry.get_schemas()

    logger.info(f"📦 Converting {len(internal_schemas)} tools to OpenAI format")

    # Convert to OpenAI format
    openai_tools = convert_tools_to_openai_format(internal_schemas)

    # Log statistics
    logger.info(f"✅ Converted {len(openai_tools)} tools:")
    for tool in openai_tools:
        name = tool["function"]["name"]
        param_count = len(tool["function"]["parameters"]["properties"])
        logger.info(f"   - {name} ({param_count} parameters)")

    return openai_tools


def add_strategic_tools(concrete_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add strategic decision tools (ask_human, complete_task) to concrete tools

    These are meta-tools that help with workflow control, not concrete actions.

    Args:
        concrete_tools: List of concrete action tools

    Returns:
        Combined list with strategic tools added
    """
    strategic_tools = [
        {
            "type": "function",
            "function": {
                "name": "ask_human",
                "description": (
                    "Ask the human user for STRATEGIC decisions only. Use this when:\n"
                    "- Multiple valid architectural approaches exist (e.g., REST vs GraphQL)\n"
                    "- Potentially dangerous operation needs confirmation (delete files, drop database)\n"
                    "- Important decision with significant business impact\n"
                    "- Entering plan mode for complex tasks\n"
                    "\n"
                    "DO NOT use for information gathering - use read_file, web_search, "
                    "or other tools to get information yourself.\n"
                    "\n"
                    "Example GOOD use: 'Should I use JWT or session-based auth?' (strategic)\n"
                    "Example BAD use: 'What's in config.py?' (use read_file instead)"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Clear, concise strategic question"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why this requires human decision (explain the strategic impact)"
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "2-4 valid options with trade-offs (optional)"
                        },
                        "recommendation": {
                            "type": "string",
                            "description": "Your recommended option with justification (optional)"
                        }
                    },
                    "required": ["question", "reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "complete_task",
                "description": (
                    "Mark the task as complete and provide final response to user. "
                    "Call this when you have finished all necessary work. "
                    "This will end the workflow and return your response to the user."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Brief summary of what was accomplished (1-2 sentences)"
                        },
                        "response": {
                            "type": "string",
                            "description": "Full response message to the user (can be long, use markdown)"
                        },
                        "files_modified": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of files created or modified (paths)"
                        },
                        "next_steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional suggested next steps for the user"
                        }
                    },
                    "required": ["summary", "response"]
                }
            }
        }
    ]

    return concrete_tools + strategic_tools
