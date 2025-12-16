"""
Testing Agent - Specialized in test generation and execution
"""

from typing import Dict, Any
from .base_specialized_agent import BaseSpecializedAgent, AgentCapabilities


class TestingAgent(BaseSpecializedAgent):
    """
    Agent specialized in creating and running tests.

    Capabilities:
    - Generate unit tests
    - Run test suites
    - Analyze test coverage
    - Write test fixtures
    """

    def __init__(self, session_id: str):
        capabilities = AgentCapabilities(
            can_use_tools=True,
            allowed_tools=[
                "read_file",
                "write_file",
                "run_tests",
                "execute_python",
                "lint_code"
            ],
            can_spawn_agents=False,
            max_iterations=5
        )

        super().__init__(
            agent_type="testing",
            model_name="qwen3-coder",  # Use coding model
            capabilities=capabilities,
            session_id=session_id
        )

    def get_system_prompt(self) -> str:
        return """You are a Testing Agent specialized in creating comprehensive tests.

Your responsibilities:
1. Generate unit tests for given code
2. Create integration tests
3. Write test fixtures and mocks
4. Run tests and interpret results
5. Ensure high code coverage

You have access to these tools:
- read_file: Read code to test
- write_file: Write test files
- run_tests: Execute pytest tests
- execute_python: Run Python code
- lint_code: Check code quality

Testing Best Practices:
- Follow arrange-act-assert pattern
- Use descriptive test names
- Test edge cases and error conditions
- Mock external dependencies
- Aim for high coverage (>80%)

Output Format:
Provide test results in this format:
- **Tests Created**: List of test files
- **Test Results**: Pass/fail status
- **Coverage**: Code coverage percentage
- **Issues Found**: Any bugs discovered
"""

    async def process(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate and run tests.

        Args:
            task: Testing task description
            context: Code to test and requirements

        Returns:
            Test results
        """
        results = {
            "task": task,
            "test_file": None,
            "test_results": None,
            "coverage": 0,
            "issues": []
        }

        # Example workflow:

        # 1. If source file provided, read it
        if "source_file" in context:
            source_result = await self.use_tool(
                "read_file",
                {"path": context["source_file"]}
            )
            if source_result.success:
                results["source_code"] = source_result.output

        # 2. If test file path provided, run tests
        if "test_path" in context:
            test_result = await self.use_tool(
                "run_tests",
                {"test_path": context["test_path"]}
            )
            if test_result.success:
                results["test_results"] = test_result.output
                results["passed"] = test_result.output.get("passed", False)
            else:
                results["issues"].append(test_result.error)

        # 3. If test code provided, write and run it
        if "test_code" in context and "test_file_path" in context:
            write_result = await self.use_tool(
                "write_file",
                {
                    "path": context["test_file_path"],
                    "content": context["test_code"]
                }
            )
            if write_result.success:
                results["test_file"] = context["test_file_path"]

                # Run the tests
                run_result = await self.use_tool(
                    "run_tests",
                    {"test_path": context["test_file_path"]}
                )
                results["test_results"] = run_result.output

        return results
