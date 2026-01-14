"""Process Execution Tools for Agentic 2.0

Safe command execution with safety controls:
- Shell command execution
- Python script execution
- Cross-platform support
- Timeout handling
"""

import asyncio
import logging
import sys
from typing import Optional, Dict, Any
from dataclasses import dataclass

from core.tool_safety import ToolSafetyManager

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result of a tool execution"""
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ProcessTools:
    """Process execution with safety controls

    Features:
    - Shell command execution
    - Python code execution
    - Safety validation
    - Timeout handling
    - Cross-platform compatibility

    Example:
        >>> safety = ToolSafetyManager(...)
        >>> proc = ProcessTools(safety)
        >>> result = await proc.execute_command("python --version")
        >>> print(result.output)
    """

    def __init__(
        self,
        safety_manager: ToolSafetyManager,
        default_timeout: int = 60,
    ):
        """Initialize ProcessTools

        Args:
            safety_manager: ToolSafetyManager for validation
            default_timeout: Default command timeout in seconds (default: 60)
        """
        self.safety = safety_manager
        self.default_timeout = default_timeout

        logger.info(f"⚙️  ProcessTools initialized (timeout: {default_timeout}s)")

    async def execute_command(
        self,
        command: str,
        timeout: Optional[int] = None,
        capture_output: bool = True,
    ) -> ToolResult:
        """Execute shell command

        Args:
            command: Shell command to execute
            timeout: Timeout in seconds (default: None = use default_timeout)
            capture_output: Capture stdout/stderr (default: True)

        Returns:
            ToolResult with command output or error
        """
        if timeout is None:
            timeout = self.default_timeout

        try:
            # Safety check
            violation = self.safety.check_command(command)
            if violation:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Safety violation: {violation.message}",
                    metadata={"violation": violation.violation_type.value}
                )

            logger.info(f"⚙️  Executing command: {command[:100]}")

            # Execute command
            if capture_output:
                process = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_shell(command)

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                # Decode output
                if capture_output:
                    stdout_text = stdout.decode('utf-8', errors='replace') if stdout else ""
                    stderr_text = stderr.decode('utf-8', errors='replace') if stderr else ""

                    # Combine output
                    combined_output = stdout_text
                    if stderr_text:
                        combined_output += f"\n[stderr]\n{stderr_text}"

                    success = process.returncode == 0

                    if success:
                        logger.info(f"✅ Command completed (exit code: 0)")
                    else:
                        logger.warning(f"⚠️  Command failed (exit code: {process.returncode})")

                    return ToolResult(
                        success=success,
                        output=combined_output.strip(),
                        error=None if success else f"Command exited with code {process.returncode}",
                        metadata={
                            "command": command,
                            "return_code": process.returncode,
                            "stdout_lines": len(stdout_text.splitlines()) if stdout_text else 0,
                            "stderr_lines": len(stderr_text.splitlines()) if stderr_text else 0,
                        }
                    )
                else:
                    # No output capture
                    success = process.returncode == 0
                    return ToolResult(
                        success=success,
                        output="Command executed (output not captured)",
                        error=None if success else f"Command exited with code {process.returncode}",
                        metadata={"command": command, "return_code": process.returncode}
                    )

            except asyncio.TimeoutError:
                # Kill process on timeout
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass

                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Command timed out after {timeout}s",
                    metadata={"command": command, "timeout": timeout}
                )

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def execute_python(
        self,
        code: str,
        timeout: Optional[int] = None,
    ) -> ToolResult:
        """Execute Python code

        Args:
            code: Python code to execute
            timeout: Timeout in seconds (default: None = use default_timeout)

        Returns:
            ToolResult with execution output or error
        """
        if timeout is None:
            timeout = self.default_timeout

        try:
            # Build python command
            python_exe = sys.executable
            command = f'{python_exe} -c "{code}"'

            # Safety check
            violation = self.safety.check_command(command)
            if violation:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Safety violation: {violation.message}",
                    metadata={"violation": violation.violation_type.value}
                )

            logger.info(f"🐍 Executing Python code ({len(code)} chars)")

            # Execute Python code
            process = await asyncio.create_subprocess_exec(
                python_exe,
                "-c",
                code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )

                stdout_text = stdout.decode('utf-8', errors='replace') if stdout else ""
                stderr_text = stderr.decode('utf-8', errors='replace') if stderr else ""

                # Combine output
                combined_output = stdout_text
                if stderr_text:
                    combined_output += f"\n[stderr]\n{stderr_text}"

                success = process.returncode == 0

                if success:
                    logger.info(f"✅ Python code executed successfully")
                else:
                    logger.warning(f"⚠️  Python code failed (exit code: {process.returncode})")

                return ToolResult(
                    success=success,
                    output=combined_output.strip(),
                    error=None if success else f"Execution failed with code {process.returncode}",
                    metadata={
                        "return_code": process.returncode,
                        "code_length": len(code),
                    }
                )

            except asyncio.TimeoutError:
                # Kill process on timeout
                try:
                    process.kill()
                    await process.wait()
                except:
                    pass

                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Python execution timed out after {timeout}s",
                    metadata={"timeout": timeout}
                )

        except Exception as e:
            logger.error(f"Error executing Python code: {e}")
            return ToolResult(success=False, output=None, error=str(e))

    async def check_command_available(self, command: str) -> ToolResult:
        """Check if a command is available in PATH

        Args:
            command: Command name to check (e.g., "git", "python")

        Returns:
            ToolResult with boolean output
        """
        try:
            import shutil
            available = shutil.which(command) is not None

            return ToolResult(
                success=True,
                output=available,
                metadata={"command": command, "available": available}
            )

        except Exception as e:
            logger.error(f"Error checking command availability: {e}")
            return ToolResult(success=False, output=None, error=str(e))
