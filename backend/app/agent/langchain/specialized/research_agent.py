"""LangChain Research Agent - Specialized in code exploration and analysis."""
import logging
from typing import Dict, Any

from app.agent.langchain.specialized.base_langchain_agent import (
    BaseLangChainAgent,
    LangChainAgentCapabilities,
)

logger = logging.getLogger(__name__)


class LangChainResearchAgent(BaseLangChainAgent):
    """
    LangChain agent specialized in exploring codebases and gathering context.

    Capabilities:
    - Read files and search for patterns
    - Analyze project structure
    - Gather requirements and context
    - Identify similar implementations

    Uses LangGraph for ReAct-style tool usage.
    """

    def __init__(self, session_id: str):
        """Initialize LangChain Research Agent.

        Args:
            session_id: Session identifier
        """
        capabilities = LangChainAgentCapabilities(
            can_use_tools=True,
            allowed_tools=[
                "read_file",
                "search_files",
                "list_directory",
                "git_status",
                "git_log"
            ],
            can_spawn_agents=False,
            max_iterations=5,
            model_type="reasoning"  # Use reasoning model for analysis
        )

        super().__init__(
            agent_type="research",
            capabilities=capabilities,
            session_id=session_id
        )

    def get_system_prompt(self) -> str:
        """Return the system prompt for research agent."""
        return """You are a Research Agent specialized in exploring codebases.

Your responsibilities:
1. Read and analyze existing code files
2. Search for relevant code patterns and implementations
3. Understand project structure and architecture
4. Gather requirements and technical context
5. Identify similar implementations and best practices

You have access to these tools:
- read_file: Read file contents (params: path, max_size_mb)
- search_files: Search for files by glob pattern (params: pattern, path, max_results)
- list_directory: List files and directories (params: path, recursive, max_depth)
- git_status: Check repository status (no params)
- git_log: View commit history (params: max_count)

Guidelines:
- Always start with understanding the project structure using list_directory
- Look for README files and documentation
- Search for similar code before suggesting new implementations
- Provide thorough analysis with file paths and line numbers
- Document your findings clearly

When you have gathered enough information, provide a structured summary:
1. **Files Found**: List of relevant files with descriptions
2. **Key Findings**: Important discoveries about the codebase
3. **Recommendations**: Suggested approach based on your research

Think step by step and use tools to gather information before making conclusions."""


class LangChainResearchAgentFactory:
    """Factory for creating LangChain Research Agents."""

    @staticmethod
    def create(session_id: str) -> LangChainResearchAgent:
        """Create a new LangChain Research Agent.

        Args:
            session_id: Session identifier

        Returns:
            New LangChainResearchAgent instance
        """
        return LangChainResearchAgent(session_id=session_id)
