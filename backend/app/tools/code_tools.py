"""
Code Execution Tools - Safe Python code execution and testing

Phase 1: ExecutePythonTool, RunTestsTool, LintCodeTool
Phase 2.5: FormatCodeTool, ShellCommandTool, DocstringGeneratorTool
"""

import subprocess
import tempfile
import pathlib
import asyncio
import logging

from .base import BaseTool, ToolCategory, ToolResult, NetworkType

logger = logging.getLogger(__name__)


class ExecutePythonTool(BaseTool):
    """Execute Python code in a safe subprocess"""

    def __init__(self):
        super().__init__("execute_python", ToolCategory.CODE)

        # Phase 2: Network requirement - LOCAL (local code execution)
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Execute Python code safely with timeout - works offline"
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

        # Phase 2: Network requirement - LOCAL (local test execution)
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Run pytest tests on specified path - works offline"
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

        # Phase 2: Network requirement - LOCAL (local code linting)
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Lint Python code with flake8 - works offline"
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


# =============================================================================
# Phase 2.5: Additional Code Tools
# =============================================================================

class FormatCodeTool(BaseTool):
    """Format code using black (Python) or prettier (JS/TS/JSON/etc)"""

    # Supported formatters and their file extensions
    FORMATTERS = {
        "black": [".py", ".pyi"],
        "prettier": [".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".yaml", ".yml", ".css", ".html"]
    }

    def __init__(self):
        super().__init__("format_code", ToolCategory.CODE)

        # Phase 2: Network requirement - LOCAL
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Format code using black (Python) or prettier (JS/TS) - works offline"
        self.parameters = {
            "file_path": {
                "type": "string",
                "required": True,
                "description": "Path to file to format"
            },
            "check_only": {
                "type": "boolean",
                "default": False,
                "description": "Only check formatting without modifying file"
            },
            "line_length": {
                "type": "integer",
                "default": 88,
                "description": "Maximum line length (for black)"
            }
        }

    def validate_params(self, file_path: str = None, **kwargs) -> bool:
        if not file_path or not isinstance(file_path, str):
            return False
        return True

    def _detect_formatter(self, file_path: pathlib.Path) -> str | None:
        """Detect appropriate formatter based on file extension"""
        suffix = file_path.suffix.lower()

        for formatter, extensions in self.FORMATTERS.items():
            if suffix in extensions:
                return formatter

        return None

    async def execute(
        self,
        file_path: str,
        check_only: bool = False,
        line_length: int = 88
    ) -> ToolResult:
        try:
            file = pathlib.Path(file_path)

            if not file.exists():
                return ToolResult(False, None, f"File not found: {file_path}")

            # Detect formatter
            formatter = self._detect_formatter(file)

            if not formatter:
                return ToolResult(
                    False,
                    None,
                    f"No formatter available for file type: {file.suffix}"
                )

            # Build command based on formatter
            if formatter == "black":
                cmd = ["black"]
                if check_only:
                    cmd.append("--check")
                cmd.extend(["--line-length", str(line_length)])
                cmd.append(str(file))
            else:  # prettier
                cmd = ["prettier"]
                if check_only:
                    cmd.append("--check")
                else:
                    cmd.append("--write")
                cmd.append(str(file))

            # Run formatter
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            output_text = stdout.decode('utf-8')
            error_text = stderr.decode('utf-8')

            # Determine success
            if check_only:
                # Check mode: returncode 0 means already formatted
                needs_formatting = process.returncode != 0
                return ToolResult(
                    success=True,
                    output={
                        "formatted": not needs_formatting,
                        "needs_formatting": needs_formatting,
                        "formatter": formatter,
                        "stdout": output_text,
                        "stderr": error_text
                    },
                    metadata={"file_path": str(file), "check_only": True}
                )
            else:
                # Format mode: returncode 0 means success
                return ToolResult(
                    success=process.returncode == 0,
                    output={
                        "formatted": process.returncode == 0,
                        "formatter": formatter,
                        "stdout": output_text,
                        "stderr": error_text
                    },
                    metadata={"file_path": str(file), "check_only": False}
                )

        except FileNotFoundError as e:
            formatter_name = "black" if ".py" in file_path else "prettier"
            return ToolResult(
                False,
                None,
                f"{formatter_name} not found. Please install: "
                f"{'pip install black' if formatter_name == 'black' else 'npm install -g prettier'}"
            )
        except Exception as e:
            logger.error(f"Error formatting {file_path}: {str(e)}")
            return ToolResult(False, None, str(e))


class ShellCommandTool(BaseTool):
    """Execute safe shell commands with sandboxing"""

    # Allowed command patterns (whitelist approach for security)
    ALLOWED_COMMANDS = {
        # File operations (read-only)
        "ls", "cat", "head", "tail", "wc", "find", "grep", "tree",
        # Info commands
        "pwd", "whoami", "date", "uname", "env", "which", "whereis",
        # Development tools
        "git", "npm", "yarn", "pip", "python", "node", "make",
        # Network diagnostics (read-only)
        "ping", "curl", "wget",
    }

    # Dangerous patterns to block
    BLOCKED_PATTERNS = [
        "rm -rf", "rm -r", "rm *",
        "sudo", "su ",
        "> /", ">> /",
        "| sh", "| bash", "| zsh",
        "; rm", "&& rm",
        "chmod 777", "chown",
        "mkfs", "dd if=",
        ":(){ :|:& };:",  # Fork bomb
        "eval ", "exec ",
    ]

    def __init__(self):
        super().__init__("shell_command", ToolCategory.CODE)

        # Phase 2: Network requirement - LOCAL
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Execute safe shell commands with security restrictions - works offline"
        self.parameters = {
            "command": {
                "type": "string",
                "required": True,
                "description": "Shell command to execute"
            },
            "working_dir": {
                "type": "string",
                "default": None,
                "description": "Working directory for command execution"
            },
            "timeout": {
                "type": "integer",
                "default": 60,
                "description": "Command timeout in seconds (max 300)"
            }
        }

    def validate_params(self, command: str = None, **kwargs) -> bool:
        if not command or not isinstance(command, str):
            return False

        # Validate timeout
        timeout = kwargs.get("timeout", 60)
        if timeout is not None and (timeout < 1 or timeout > 300):
            return False

        return True

    def _is_command_safe(self, command: str) -> tuple[bool, str]:
        """Check if command is safe to execute

        Returns:
            tuple[bool, str]: (is_safe, reason)
        """
        # Check for blocked patterns
        command_lower = command.lower()
        for pattern in self.BLOCKED_PATTERNS:
            if pattern.lower() in command_lower:
                return False, f"Blocked pattern detected: {pattern}"

        # Check if command starts with allowed command
        first_word = command.split()[0] if command.split() else ""
        base_command = first_word.split("/")[-1]  # Handle full paths

        if base_command not in self.ALLOWED_COMMANDS:
            return False, f"Command not in allowlist: {base_command}"

        return True, "OK"

    async def execute(
        self,
        command: str,
        working_dir: str = None,
        timeout: int = 60
    ) -> ToolResult:
        try:
            # Security check
            is_safe, reason = self._is_command_safe(command)
            if not is_safe:
                return ToolResult(
                    False,
                    None,
                    f"Security check failed: {reason}"
                )

            # Validate working directory
            cwd = None
            if working_dir:
                cwd = pathlib.Path(working_dir)
                if not cwd.exists() or not cwd.is_dir():
                    return ToolResult(
                        False,
                        None,
                        f"Working directory not found: {working_dir}"
                    )
                cwd = str(cwd)

            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=min(timeout, 300)  # Cap at 300s
                )

                return ToolResult(
                    success=process.returncode == 0,
                    output={
                        "stdout": stdout.decode('utf-8'),
                        "stderr": stderr.decode('utf-8'),
                        "returncode": process.returncode,
                        "command": command
                    },
                    metadata={
                        "working_dir": cwd or "current",
                        "timeout": timeout
                    }
                )

            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    False,
                    None,
                    f"Command timeout ({timeout}s): {command}"
                )

        except Exception as e:
            logger.error(f"Error executing command '{command}': {str(e)}")
            return ToolResult(False, None, str(e))


class DocstringGeneratorTool(BaseTool):
    """Generate docstrings for Python functions/classes using AST analysis"""

    def __init__(self):
        super().__init__("generate_docstring", ToolCategory.CODE)

        # Phase 2: Network requirement - LOCAL
        self.requires_network = False
        self.network_type = NetworkType.LOCAL

        self.description = "Generate Python docstrings by analyzing function signatures - works offline"
        self.parameters = {
            "file_path": {
                "type": "string",
                "required": True,
                "description": "Path to Python file"
            },
            "function_name": {
                "type": "string",
                "required": False,
                "description": "Specific function/class name (optional, generates for all if not specified)"
            },
            "style": {
                "type": "string",
                "default": "google",
                "description": "Docstring style: google, numpy, or sphinx"
            }
        }

    def validate_params(self, file_path: str = None, **kwargs) -> bool:
        if not file_path or not isinstance(file_path, str):
            return False

        style = kwargs.get("style", "google")
        if style not in ["google", "numpy", "sphinx"]:
            return False

        return True

    def _generate_google_style(self, func_info: dict) -> str:
        """Generate Google-style docstring"""
        lines = ['"""']

        # Summary
        lines.append(f"TODO: Add description for {func_info['name']}")
        lines.append("")

        # Args
        if func_info["args"]:
            lines.append("Args:")
            for arg in func_info["args"]:
                arg_type = arg.get("type", "Any")
                lines.append(f"    {arg['name']} ({arg_type}): TODO: Add description")

        # Returns
        if func_info.get("returns"):
            lines.append("")
            lines.append("Returns:")
            lines.append(f"    {func_info['returns']}: TODO: Add description")

        # Raises
        if func_info.get("raises"):
            lines.append("")
            lines.append("Raises:")
            for exc in func_info["raises"]:
                lines.append(f"    {exc}: TODO: Add description")

        lines.append('"""')
        return "\n".join(lines)

    def _generate_numpy_style(self, func_info: dict) -> str:
        """Generate NumPy-style docstring"""
        lines = ['"""']

        # Summary
        lines.append(f"TODO: Add description for {func_info['name']}")
        lines.append("")

        # Parameters
        if func_info["args"]:
            lines.append("Parameters")
            lines.append("----------")
            for arg in func_info["args"]:
                arg_type = arg.get("type", "Any")
                lines.append(f"{arg['name']} : {arg_type}")
                lines.append("    TODO: Add description")

        # Returns
        if func_info.get("returns"):
            lines.append("")
            lines.append("Returns")
            lines.append("-------")
            lines.append(f"{func_info['returns']}")
            lines.append("    TODO: Add description")

        lines.append('"""')
        return "\n".join(lines)

    def _generate_sphinx_style(self, func_info: dict) -> str:
        """Generate Sphinx-style docstring"""
        lines = ['"""']

        # Summary
        lines.append(f"TODO: Add description for {func_info['name']}")
        lines.append("")

        # Parameters
        for arg in func_info["args"]:
            arg_type = arg.get("type", "Any")
            lines.append(f":param {arg['name']}: TODO: Add description")
            lines.append(f":type {arg['name']}: {arg_type}")

        # Returns
        if func_info.get("returns"):
            lines.append(f":returns: TODO: Add description")
            lines.append(f":rtype: {func_info['returns']}")

        # Raises
        if func_info.get("raises"):
            for exc in func_info["raises"]:
                lines.append(f":raises {exc}: TODO: Add description")

        lines.append('"""')
        return "\n".join(lines)

    async def execute(
        self,
        file_path: str,
        function_name: str = None,
        style: str = "google"
    ) -> ToolResult:
        try:
            import ast

            file = pathlib.Path(file_path)

            if not file.exists():
                return ToolResult(False, None, f"File not found: {file_path}")

            if not file.suffix == ".py":
                return ToolResult(False, None, "Only Python files are supported")

            # Parse the file
            source = file.read_text(encoding='utf-8')
            tree = ast.parse(source)

            # Extract function/class info
            results = []

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip if specific function requested and this isn't it
                    if function_name and node.name != function_name:
                        continue

                    # Skip if already has docstring
                    if ast.get_docstring(node):
                        continue

                    # Extract function info
                    func_info = {
                        "name": node.name,
                        "lineno": node.lineno,
                        "is_async": isinstance(node, ast.AsyncFunctionDef),
                        "args": [],
                        "returns": None,
                        "raises": []
                    }

                    # Parse arguments
                    for arg in node.args.args:
                        if arg.arg == "self" or arg.arg == "cls":
                            continue
                        arg_info = {"name": arg.arg}
                        if arg.annotation:
                            arg_info["type"] = ast.unparse(arg.annotation)
                        func_info["args"].append(arg_info)

                    # Parse return annotation
                    if node.returns:
                        func_info["returns"] = ast.unparse(node.returns)

                    # Detect raise statements
                    for child in ast.walk(node):
                        if isinstance(child, ast.Raise) and child.exc:
                            if isinstance(child.exc, ast.Call):
                                if hasattr(child.exc.func, 'id'):
                                    func_info["raises"].append(child.exc.func.id)

                    # Generate docstring
                    if style == "numpy":
                        docstring = self._generate_numpy_style(func_info)
                    elif style == "sphinx":
                        docstring = self._generate_sphinx_style(func_info)
                    else:
                        docstring = self._generate_google_style(func_info)

                    results.append({
                        "name": func_info["name"],
                        "lineno": func_info["lineno"],
                        "is_async": func_info["is_async"],
                        "docstring": docstring
                    })

                elif isinstance(node, ast.ClassDef):
                    if function_name and node.name != function_name:
                        continue

                    if ast.get_docstring(node):
                        continue

                    # Generate simple class docstring
                    docstring = f'"""\nTODO: Add description for {node.name}\n"""'

                    results.append({
                        "name": node.name,
                        "lineno": node.lineno,
                        "is_class": True,
                        "docstring": docstring
                    })

            if not results:
                if function_name:
                    return ToolResult(
                        success=True,
                        output={
                            "generated": [],
                            "message": f"Function/class '{function_name}' not found or already has docstring"
                        }
                    )
                else:
                    return ToolResult(
                        success=True,
                        output={
                            "generated": [],
                            "message": "All functions/classes already have docstrings"
                        }
                    )

            return ToolResult(
                success=True,
                output={
                    "generated": results,
                    "count": len(results),
                    "style": style
                },
                metadata={"file_path": str(file)}
            )

        except SyntaxError as e:
            return ToolResult(False, None, f"Python syntax error: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating docstrings for {file_path}: {str(e)}")
            return ToolResult(False, None, str(e))
