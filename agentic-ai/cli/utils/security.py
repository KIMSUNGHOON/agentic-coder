"""Security Checker

Enforces local-only data policy and validates inputs.
"""

import os
import socket
import re
from typing import List, Optional
from pathlib import Path


class SecurityChecker:
    """Security validation for CLI

    Enforces:
    - Local-only data storage
    - No external network access
    - Input validation
    - Path traversal prevention
    """

    # Allowed local hosts
    ALLOWED_HOSTS = [
        "localhost",
        "127.0.0.1",
        "::1",
    ]

    # Blocked patterns in input
    BLOCKED_PATTERNS = [
        r"http[s]?://(?!localhost|127\.0\.0\.1)",  # External URLs
        r"eval\s*\(",  # Eval statements
        r"exec\s*\(",  # Exec statements
        r"__import__",  # Dynamic imports
        r"\.\./",  # Path traversal
    ]

    def __init__(self):
        """Initialize security checker"""
        # Add vLLM server IP if configured
        vllm_ip = os.getenv("VLLM_SERVER_IP")
        if vllm_ip:
            self.ALLOWED_HOSTS.append(vllm_ip)

    def check_local_only(self) -> bool:
        """Check if running in local-only mode

        Returns:
            True if local-only, False if external access detected
        """
        try:
            # Try to resolve external DNS (should fail if isolated)
            socket.gethostbyname("api.openai.com")
            # If successful, external access is possible
            return False
        except socket.gaierror:
            # DNS resolution failed - good, we're isolated
            return True
        except Exception:
            # Other errors - assume not isolated
            return False

    def validate_input(self, text: str) -> bool:
        """Validate user input

        Args:
            text: User input text

        Returns:
            True if safe, False if blocked
        """
        # Check for blocked patterns
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False

        return True

    def validate_file_path(self, path: str) -> bool:
        """Validate file path (prevent traversal)

        Args:
            path: File path

        Returns:
            True if safe, False if blocked
        """
        try:
            # Resolve absolute path
            abs_path = Path(path).resolve()

            # Check if within workspace
            workspace = Path("./workspace").resolve()
            data_dir = Path("./data").resolve()
            logs_dir = Path("./logs").resolve()

            # Path must be under one of these directories
            allowed = [workspace, data_dir, logs_dir]

            for allowed_dir in allowed:
                try:
                    abs_path.relative_to(allowed_dir)
                    return True
                except ValueError:
                    continue

            # Not under any allowed directory
            return False

        except Exception:
            # Error resolving path
            return False

    def validate_endpoint(self, url: str) -> bool:
        """Validate endpoint URL (must be local)

        Args:
            url: Endpoint URL

        Returns:
            True if local, False if external
        """
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            hostname = parsed.hostname

            if not hostname:
                return False

            # Check if in allowed hosts
            if hostname in self.ALLOWED_HOSTS:
                return True

            # Check if it's a private IP
            if self._is_private_ip(hostname):
                return True

            return False

        except Exception:
            return False

    def _is_private_ip(self, ip: str) -> bool:
        """Check if IP is private

        Args:
            ip: IP address

        Returns:
            True if private IP
        """
        try:
            import ipaddress
            addr = ipaddress.ip_address(ip)
            return addr.is_private
        except:
            return False

    def sanitize_output(self, text: str) -> str:
        """Sanitize output text (remove sensitive data)

        Args:
            text: Output text

        Returns:
            Sanitized text
        """
        # Mask potential API keys
        text = re.sub(
            r"(api[_-]?key|token|password)[\s:=]+['\"]?[\w-]{20,}['\"]?",
            r"\1=***MASKED***",
            text,
            flags=re.IGNORECASE
        )

        # Mask file paths outside workspace
        text = re.sub(
            r"/home/[^/\s]+",
            "/home/***",
            text
        )

        return text

    def log_security_event(self, event: str) -> None:
        """Log security event (local file only)

        Args:
            event: Security event description
        """
        try:
            log_file = Path("./logs/security.jsonl")
            log_file.parent.mkdir(parents=True, exist_ok=True)

            import json
            from datetime import datetime

            entry = {
                "timestamp": datetime.now().isoformat(),
                "event": event,
                "severity": "warning"
            }

            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        except Exception as e:
            print(f"Warning: Could not log security event: {e}")
