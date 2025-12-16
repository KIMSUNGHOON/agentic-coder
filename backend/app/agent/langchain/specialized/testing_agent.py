"""LangChain Testing Agent - Specialized in test generation and execution."""
import logging
from typing import Dict, Any

from app.agent.langchain.specialized.base_langchain_agent import (
    BaseLangChainAgent,
    LangChainAgentCapabilities,
)

logger = logging.getLogger(__name__)


class LangChainTestingAgent(BaseLangChainAgent):
    """
    LangChain agent specialized in generating and running tests.

    Capabilities:
    - Read source code
    - Generate unit tests
    - Execute test suites
    - Lint and validate code

    Uses LangGraph for ReAct-style tool usage.
    """

    def __init__(self, session_id: str):
        """Initialize LangChain Testing Agent.

        Args:
            session_id: Session identifier
        """
        capabilities = LangChainAgentCapabilities(
            can_use_tools=True,
            allowed_tools=[
                "read_file",
                "write_file",
                "run_tests",
                "execute_python",
                "lint_code"
            ],
            can_spawn_agents=False,
            max_iterations=5,
            model_type="coding"  # Use coding model for test generation
        )

        super().__init__(
            agent_type="testing",
            capabilities=capabilities,
            session_id=session_id
        )

    def get_system_prompt(self) -> str:
        """Return the system prompt for testing agent."""
        return """You are a Testing Agent specialized in generating and running tests.

Your responsibilities:
1. Read and understand source code
2. Generate comprehensive unit tests
3. Execute test suites and report results
4. Lint code for quality issues
5. Identify edge cases and potential bugs

You have access to these tools:
- read_file: Read file contents (params: path, max_size_mb)
- write_file: Write content to file (params: path, content, create_dirs)
- run_tests: Run pytest tests (params: test_path, timeout, verbose)
- execute_python: Execute Python code safely (params: code, timeout)
- lint_code: Lint Python with flake8 (params: file_path)

Guidelines for test generation:
- Follow pytest conventions
- Use descriptive test names: test_<function>_<scenario>_<expected>
- Include docstrings explaining what each test verifies
- Cover:
  * Happy path cases
  * Edge cases (empty inputs, None values)
  * Error conditions
  * Boundary values
- Use fixtures and parametrize for test organization
- Mock external dependencies

Workflow:
1. First, read the source code to understand the implementation
2. Identify functions/classes to test
3. Generate test code
4. Run the tests to verify they work
5. Report results with any issues found

When generating tests, output the complete test file content that can be saved directly."""


class LangChainTestingAgentFactory:
    """Factory for creating LangChain Testing Agents."""

    @staticmethod
    def create(session_id: str) -> LangChainTestingAgent:
        """Create a new LangChain Testing Agent.

        Args:
            session_id: Session identifier

        Returns:
            New LangChainTestingAgent instance
        """
        return LangChainTestingAgent(session_id=session_id)
