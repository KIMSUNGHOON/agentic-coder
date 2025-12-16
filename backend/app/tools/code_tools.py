"""
Code Execution Tools - Safe Python code execution and testing
"""

import subprocess
import tempfile
import pathlib
import asyncio
import logging

from .base import BaseTool, ToolCategory, ToolResult

logger = logging.getLogger(__name__)


class ExecutePythonTool(BaseTool):
    """Execute Python code in a safe subprocess"""

    def __init__(self):
        super().__init__("execute_python", ToolCategory.CODE)
        self.description = "Execute Python code safely with timeout"
        self.parameters = {
            "code": {
                "type": "string",
                "required": True,
                "description": "Python code to execute"
            },
            "timeout": {
                "type": "number",
                "default": 30,
                "description": "Execution timeout in seconds"
            }
        }

    def validate_params(self, code: str, **kwargs) -> bool:
        return isinstance(code, str) and len(code) > 0

    async def execute(self, code: str, timeout: int = 30) -> ToolResult:
        temp_path = None
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False,
                encoding='utf-8'
            ) as f:
                f.write(code)
                temp_path = f.name

            # Execute in subprocess with timeout
            process = await asyncio.create_subprocess_exec(
                'python3', temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                return ToolResult(
                    success=process.returncode == 0,
                    output={
                        "stdout": stdout.decode('utf-8'),
                        "stderr": stderr.decode('utf-8'),
                        "returncode": process.returncode
                    },
                    metadata={
                        "code_lines": len(code.splitlines())
                    }
                )

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    False,
                    None,
                    f"Execution timeout ({timeout}s)"
                )

        except Exception as e:
            logger.error(f"Error executing Python code: {str(e)}")
            return ToolResult(False, None, str(e))

        finally:
            # Clean up temp file
            if temp_path and pathlib.Path(temp_path).exists():
                pathlib.Path(temp_path).unlink(missing_ok=True)


class RunTestsTool(BaseTool):
    """Run pytest tests"""

    def __init__(self):
        super().__init__("run_tests", ToolCategory.CODE)
        self.description = "Run pytest tests on specified path"
        self.parameters = {
            "test_path": {
                "type": "string",
                "required": True,
                "description": "Path to test file or directory"
            },
            "timeout": {
                "type": "number",
                "default": 300,
                "description": "Test execution timeout in seconds"
            },
            "verbose": {
                "type": "boolean",
                "default": True,
                "description": "Verbose output"
            }
        }

    def validate_params(self, test_path: str, **kwargs) -> bool:
        return isinstance(test_path, str)

    async def execute(
        self,
        test_path: str,
        timeout: int = 300,
        verbose: bool = True
    ) -> ToolResult:
        try:
            test_file = pathlib.Path(test_path)

            if not test_file.exists():
                return ToolResult(False, None, f"Test path not found: {test_path}")

            # Build pytest command
            cmd = ['pytest', str(test_file)]
            if verbose:
                cmd.append('-v')
            cmd.extend(['--tb=short', '--color=yes'])

            # Run tests
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                output_text = stdout.decode('utf-8')
                error_text = stderr.decode('utf-8')

                # Parse results (basic parsing)
                passed = "passed" in output_text
                failed = "failed" in output_text

                return ToolResult(
                    success=process.returncode == 0,
                    output={
                        "stdout": output_text,
                        "stderr": error_text,
                        "passed": passed and not failed,
                        "returncode": process.returncode
                    },
                    metadata={
                        "test_path": str(test_file)
                    }
                )

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    False,
                    None,
                    f"Test execution timeout ({timeout}s)"
                )

        except FileNotFoundError:
            return ToolResult(
                False,
                None,
                "pytest not found. Please install pytest: pip install pytest"
            )
        except Exception as e:
            logger.error(f"Error running tests {test_path}: {str(e)}")
            return ToolResult(False, None, str(e))


class LintCodeTool(BaseTool):
    """Run code linting with flake8 or ruff"""

    def __init__(self):
        super().__init__("lint_code", ToolCategory.CODE)
        self.description = "Lint Python code with flake8"
        self.parameters = {
            "file_path": {
                "type": "string",
                "required": True,
                "description": "Path to Python file to lint"
            }
        }

    def validate_params(self, file_path: str, **kwargs) -> bool:
        return isinstance(file_path, str)

    async def execute(self, file_path: str) -> ToolResult:
        try:
            file = pathlib.Path(file_path)

            if not file.exists():
                return ToolResult(False, None, f"File not found: {file_path}")

            # Try flake8 first
            process = await asyncio.create_subprocess_exec(
                'flake8', str(file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()
            output = stdout.decode('utf-8')

            issues = output.strip().split('\n') if output.strip() else []

            return ToolResult(
                success=len(issues) == 0,
                output={
                    "issues": issues,
                    "count": len(issues),
                    "clean": len(issues) == 0
                },
                metadata={
                    "file_path": str(file)
                }
            )

        except FileNotFoundError:
            return ToolResult(
                False,
                None,
                "flake8 not found. Please install: pip install flake8"
            )
        except Exception as e:
            logger.error(f"Error linting {file_path}: {str(e)}")
            return ToolResult(False, None, str(e))
