"""Tool Safety Module for Agentic 2.0

Provides security controls for tool execution:
- Command allowlist/denylist enforcement
- Protected file and pattern detection
- Path traversal prevention
- Cross-platform compatibility (Windows/macOS/Linux)

All tools must pass safety checks before execution.
"""

import re
import os
import logging
from pathlib import Path
from typing import List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ViolationType(str, Enum):
    """Types of safety violations"""
    DENIED_COMMAND = "denied_command"
    DISALLOWED_COMMAND = "disallowed_command"
    PROTECTED_FILE = "protected_file"
    PROTECTED_PATTERN = "protected_pattern"
    PATH_TRAVERSAL = "path_traversal"
    SUSPICIOUS_OPERATION = "suspicious_operation"


@dataclass
class SafetyViolation:
    """Represents a safety policy violation"""
    violation_type: ViolationType
    message: str
    details: str
    suggested_action: Optional[str] = None


class ToolSafetyManager:
    """Enforces safety policies for tool execution

    Features:
    - Command allowlist/denylist
    - Protected file patterns
    - Path traversal detection
    - Dangerous operation detection
    - Cross-platform support

    Example:
        >>> config = {
        ...     "enabled": True,
        ...     "command_allowlist": ["python", "git", "npm"],
        ...     "command_denylist": ["rm -rf /", "dd if="],
        ...     "protected_files": ["/etc/passwd", "~/.ssh"],
        ...     "protected_patterns": ["*.key", "*.pem", ".env"]
        ... }
        >>> safety = ToolSafetyManager(config)
        >>> result = safety.check_command("python script.py")
        >>> if result:
        ...     print(f"Violation: {result.message}")
    """

    # Dangerous command patterns (regex)
    DANGEROUS_PATTERNS = [
        r'\brm\s+-rf\s+/',  # rm -rf /
        r'\bdd\s+if=',  # dd if=... (disk operations)
        r':\(\)\{.*?\}:',  # Fork bombs
        r'\bmkfs\.',  # Format filesystem
        r'\b(?:sudo\s+)?chmod\s+777',  # Overly permissive permissions
        r'>\s*/dev/sd[a-z]',  # Write to block device
        r'\bcurl\s+.*\|\s*(?:bash|sh)',  # Curl pipe to shell
        r'\bwget\s+.*\|\s*(?:bash|sh)',  # Wget pipe to shell
        r'\beval\s+.*\$\(',  # Dangerous eval
        r';\s*rm\s+-rf',  # Chained rm -rf
    ]

    # Suspicious file operations (case-insensitive)
    SUSPICIOUS_PATHS = [
        "/etc/passwd",
        "/etc/shadow",
        "/etc/sudoers",
        "/boot",
        "/sys",
        "/proc",
        "C:\\Windows\\System32",
        "C:\\Windows\\SysWOW64",
    ]

    def __init__(
        self,
        enabled: bool = True,
        command_allowlist: Optional[List[str]] = None,
        command_denylist: Optional[List[str]] = None,
        protected_files: Optional[List[str]] = None,
        protected_patterns: Optional[List[str]] = None,
    ):
        """Initialize ToolSafetyManager

        Args:
            enabled: Enable safety checks (default: True)
            command_allowlist: List of allowed command prefixes (e.g., ["python", "git"])
            command_denylist: List of denied command patterns (e.g., ["rm -rf /"])
            protected_files: List of protected file paths
            protected_patterns: List of protected glob patterns (e.g., ["*.key", ".env"])
        """
        self.enabled = enabled

        # Normalize allowlist/denylist
        self.command_allowlist = set(command_allowlist or [])
        self.command_denylist = set(command_denylist or [])

        # Protected files and patterns
        self.protected_files = set(protected_files or [])
        self.protected_patterns = protected_patterns or []

        # Compile dangerous patterns
        self.dangerous_regexes = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.DANGEROUS_PATTERNS
        ]

        # Statistics
        self.total_checks = 0
        self.total_violations = 0
        self.violations_by_type = {vtype: 0 for vtype in ViolationType}

        if enabled:
            logger.info(
                f"🛡️  Tool Safety Manager initialized:\n"
                f"   - Allowlist: {len(self.command_allowlist)} commands\n"
                f"   - Denylist: {len(self.command_denylist)} patterns\n"
                f"   - Protected files: {len(self.protected_files)}\n"
                f"   - Protected patterns: {len(self.protected_patterns)}"
            )
        else:
            logger.warning("⚠️  Tool Safety Manager is DISABLED")

    def check_command(self, command: str) -> Optional[SafetyViolation]:
        """Check if command is safe to execute

        Args:
            command: Shell command to check

        Returns:
            SafetyViolation if unsafe, None if safe
        """
        if not self.enabled:
            return None

        self.total_checks += 1

        # Extract base command (first token)
        base_command = command.strip().split()[0] if command.strip() else ""

        # Check against denylist
        for denied in self.command_denylist:
            if denied.lower() in command.lower():
                violation = SafetyViolation(
                    violation_type=ViolationType.DENIED_COMMAND,
                    message=f"Command contains denied pattern: {denied}",
                    details=f"Command: {command}",
                    suggested_action="Remove the denied pattern or request administrator approval",
                )
                self._record_violation(violation)
                return violation

        # Check against allowlist (if configured)
        if self.command_allowlist:
            allowed = any(
                base_command.lower().startswith(allowed_cmd.lower())
                for allowed_cmd in self.command_allowlist
            )

            if not allowed:
                violation = SafetyViolation(
                    violation_type=ViolationType.DISALLOWED_COMMAND,
                    message=f"Command '{base_command}' is not in allowlist",
                    details=f"Allowed commands: {', '.join(sorted(self.command_allowlist))}",
                    suggested_action="Use an allowed command or add to allowlist",
                )
                self._record_violation(violation)
                return violation

        # Check for dangerous patterns
        for regex in self.dangerous_regexes:
            if regex.search(command):
                violation = SafetyViolation(
                    violation_type=ViolationType.SUSPICIOUS_OPERATION,
                    message=f"Command contains dangerous pattern",
                    details=f"Command: {command}",
                    suggested_action="Review command for potential destructive operations",
                )
                self._record_violation(violation)
                return violation

        # Check for suspicious paths
        for suspicious_path in self.SUSPICIOUS_PATHS:
            if suspicious_path.lower() in command.lower():
                violation = SafetyViolation(
                    violation_type=ViolationType.SUSPICIOUS_OPERATION,
                    message=f"Command accesses suspicious system path: {suspicious_path}",
                    details=f"Command: {command}",
                    suggested_action="Avoid modifying critical system directories",
                )
                self._record_violation(violation)
                return violation

        # Safe
        return None

    def check_file_access(
        self,
        file_path: str,
        operation: str = "read",
    ) -> Optional[SafetyViolation]:
        """Check if file access is safe

        Args:
            file_path: Path to file
            operation: Type of operation (read, write, delete, etc.)

        Returns:
            SafetyViolation if unsafe, None if safe
        """
        if not self.enabled:
            return None

        self.total_checks += 1

        # Normalize path
        try:
            normalized_path = str(Path(file_path).resolve())
        except Exception as e:
            logger.warning(f"Could not normalize path: {file_path} - {e}")
            normalized_path = file_path

        # Check for path traversal
        if ".." in file_path or "~" in file_path:
            # Allow ~ for home directory, but check if it resolves safely
            if "~" in file_path:
                try:
                    expanded = os.path.expanduser(file_path)
                    if ".." in expanded:
                        violation = SafetyViolation(
                            violation_type=ViolationType.PATH_TRAVERSAL,
                            message="Path contains traversal after expansion",
                            details=f"Original: {file_path}, Expanded: {expanded}",
                            suggested_action="Use absolute paths",
                        )
                        self._record_violation(violation)
                        return violation
                except Exception:
                    pass

        # Check protected files
        for protected in self.protected_files:
            # Expand ~ in protected path
            protected_expanded = os.path.expanduser(protected)

            if (
                normalized_path == protected_expanded
                or normalized_path.startswith(protected_expanded + os.sep)
            ):
                violation = SafetyViolation(
                    violation_type=ViolationType.PROTECTED_FILE,
                    message=f"Access to protected path: {protected}",
                    details=f"Operation: {operation}, Path: {file_path}",
                    suggested_action="This path is protected by policy",
                )
                self._record_violation(violation)
                return violation

        # Check protected patterns
        file_name = Path(file_path).name
        for pattern in self.protected_patterns:
            # Simple glob pattern matching
            if self._matches_pattern(file_name, pattern):
                violation = SafetyViolation(
                    violation_type=ViolationType.PROTECTED_PATTERN,
                    message=f"File matches protected pattern: {pattern}",
                    details=f"Operation: {operation}, File: {file_name}",
                    suggested_action="This file type is protected by policy",
                )
                self._record_violation(violation)
                return violation

        # Check for suspicious system paths
        for suspicious_path in self.SUSPICIOUS_PATHS:
            if normalized_path.lower().startswith(suspicious_path.lower()):
                violation = SafetyViolation(
                    violation_type=ViolationType.SUSPICIOUS_OPERATION,
                    message=f"Access to critical system path: {suspicious_path}",
                    details=f"Operation: {operation}, Path: {file_path}",
                    suggested_action="Avoid accessing critical system directories",
                )
                self._record_violation(violation)
                return violation

        # Safe
        return None

    def _matches_pattern(self, filename: str, pattern: str) -> bool:
        """Check if filename matches glob pattern

        Args:
            filename: Filename to check
            pattern: Glob pattern (e.g., "*.key", ".env")

        Returns:
            True if matches, False otherwise
        """
        # Convert glob pattern to regex
        regex_pattern = pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
        regex_pattern = f"^{regex_pattern}$"

        return bool(re.match(regex_pattern, filename, re.IGNORECASE))

    def _record_violation(self, violation: SafetyViolation):
        """Record a safety violation for statistics

        Args:
            violation: The violation to record
        """
        self.total_violations += 1
        self.violations_by_type[violation.violation_type] += 1

        logger.warning(
            f"🚨 Safety Violation: {violation.violation_type.value}\n"
            f"   Message: {violation.message}\n"
            f"   Details: {violation.details}"
        )

    def get_stats(self) -> dict:
        """Get safety check statistics

        Returns:
            Dictionary with statistics
        """
        violation_rate = (
            self.total_violations / self.total_checks
            if self.total_checks > 0
            else 0.0
        )

        return {
            "enabled": self.enabled,
            "total_checks": self.total_checks,
            "total_violations": self.total_violations,
            "violation_rate": violation_rate,
            "violations_by_type": {
                vtype.value: count
                for vtype, count in self.violations_by_type.items()
                if count > 0
            },
            "policy": {
                "command_allowlist_size": len(self.command_allowlist),
                "command_denylist_size": len(self.command_denylist),
                "protected_files": len(self.protected_files),
                "protected_patterns": len(self.protected_patterns),
            },
        }

    def is_safe_command(self, command: str) -> bool:
        """Quick check if command is safe (returns boolean)

        Args:
            command: Command to check

        Returns:
            True if safe, False if unsafe
        """
        return self.check_command(command) is None

    def is_safe_file_access(self, file_path: str, operation: str = "read") -> bool:
        """Quick check if file access is safe (returns boolean)

        Args:
            file_path: Path to check
            operation: Operation type

        Returns:
            True if safe, False if unsafe
        """
        return self.check_file_access(file_path, operation) is None


# Convenience function
def create_safety_manager_from_config(config: dict) -> ToolSafetyManager:
    """Create ToolSafetyManager from configuration dict

    Args:
        config: Configuration dictionary with 'tools.safety' section

    Returns:
        Initialized ToolSafetyManager

    Example:
        >>> config = {
        ...     "tools": {
        ...         "safety": {
        ...             "enabled": True,
        ...             "command_allowlist": ["python", "git"],
        ...             "command_denylist": ["rm -rf /"],
        ...             "protected_files": ["/etc/passwd"],
        ...             "protected_patterns": ["*.key"]
        ...         }
        ...     }
        ... }
        >>> safety = create_safety_manager_from_config(config)
    """
    safety_config = config["tools"]["safety"]

    return ToolSafetyManager(
        enabled=safety_config.get("enabled", True),
        command_allowlist=safety_config.get("command_allowlist", []),
        command_denylist=safety_config.get("command_denylist", []),
        protected_files=safety_config.get("protected_files", []),
        protected_patterns=safety_config.get("protected_patterns", []),
    )
