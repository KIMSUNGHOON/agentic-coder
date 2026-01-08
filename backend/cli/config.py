"""CLI Configuration Management

Handles CLI configuration with support for:
- User configuration file (~/.agentic-coder/config.yaml)
- Project configuration file (.agentic-coder/config.yaml)
- Environment variable overrides
- Default configuration
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class CLIConfig:
    """CLI Configuration settings"""

    # LLM Settings
    model: str = "deepseek-r1:14b"
    api_endpoint: str = "http://localhost:8001/v1"
    max_tokens: int = 4096
    temperature: float = 0.7

    # UI Settings
    theme: str = "monokai"
    syntax_theme: str = "monokai"
    show_line_numbers: bool = True
    word_wrap: bool = False

    # History Settings
    history_file: str = "~/.agentic-coder/history"
    max_history_lines: int = 10000
    save_history: bool = True

    # Session Settings
    auto_save: bool = True
    session_dir: str = ".agentic-coder/sessions"

    # Workspace Settings
    default_workspace: str = "."
    ignore_patterns: list = field(default_factory=lambda: [
        ".git", "__pycache__", "node_modules", ".venv", "venv", ".env"
    ])

    # Network Settings
    network_mode: str = "online"  # online or offline
    timeout: int = 30

    # Debug Settings
    debug: bool = False
    verbose: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            "llm": {
                "model": self.model,
                "api_endpoint": self.api_endpoint,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            },
            "ui": {
                "theme": self.theme,
                "syntax_theme": self.syntax_theme,
                "show_line_numbers": self.show_line_numbers,
                "word_wrap": self.word_wrap
            },
            "history": {
                "file": self.history_file,
                "max_lines": self.max_history_lines,
                "save": self.save_history
            },
            "session": {
                "auto_save": self.auto_save,
                "dir": self.session_dir
            },
            "workspace": {
                "default": self.default_workspace,
                "ignore_patterns": self.ignore_patterns
            },
            "network": {
                "mode": self.network_mode,
                "timeout": self.timeout
            },
            "debug": {
                "enabled": self.debug,
                "verbose": self.verbose
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CLIConfig":
        """Create config from dictionary"""
        config = cls()

        if "llm" in data:
            llm = data["llm"]
            config.model = llm.get("model", config.model)
            config.api_endpoint = llm.get("api_endpoint", config.api_endpoint)
            config.max_tokens = llm.get("max_tokens", config.max_tokens)
            config.temperature = llm.get("temperature", config.temperature)

        if "ui" in data:
            ui = data["ui"]
            config.theme = ui.get("theme", config.theme)
            config.syntax_theme = ui.get("syntax_theme", config.syntax_theme)
            config.show_line_numbers = ui.get("show_line_numbers", config.show_line_numbers)
            config.word_wrap = ui.get("word_wrap", config.word_wrap)

        if "history" in data:
            history = data["history"]
            config.history_file = history.get("file", config.history_file)
            config.max_history_lines = history.get("max_lines", config.max_history_lines)
            config.save_history = history.get("save", config.save_history)

        if "session" in data:
            session = data["session"]
            config.auto_save = session.get("auto_save", config.auto_save)
            config.session_dir = session.get("dir", config.session_dir)

        if "workspace" in data:
            workspace = data["workspace"]
            config.default_workspace = workspace.get("default", config.default_workspace)
            config.ignore_patterns = workspace.get("ignore_patterns", config.ignore_patterns)

        if "network" in data:
            network = data["network"]
            config.network_mode = network.get("mode", config.network_mode)
            config.timeout = network.get("timeout", config.timeout)

        if "debug" in data:
            debug = data["debug"]
            config.debug = debug.get("enabled", config.debug)
            config.verbose = debug.get("verbose", config.verbose)

        return config


class ConfigManager:
    """Manages CLI configuration loading and saving"""

    USER_CONFIG_DIR = Path.home() / ".agentic-coder"
    USER_CONFIG_FILE = USER_CONFIG_DIR / "config.yaml"
    PROJECT_CONFIG_FILE = ".agentic-coder/config.yaml"

    def __init__(self, workspace: Optional[str] = None):
        """Initialize config manager

        Args:
            workspace: Optional workspace directory
        """
        self.workspace = Path(workspace or ".").resolve()
        self._config: Optional[CLIConfig] = None

    def get_config(self) -> CLIConfig:
        """Get merged configuration

        Priority (highest to lowest):
        1. Environment variables
        2. Project config
        3. User config
        4. Default config

        Returns:
            Merged CLIConfig
        """
        if self._config is not None:
            return self._config

        # Start with default config
        config = CLIConfig()

        # Load user config if exists
        if self.USER_CONFIG_FILE.exists():
            try:
                user_data = self._load_yaml(self.USER_CONFIG_FILE)
                config = CLIConfig.from_dict(user_data)
            except Exception:
                pass  # Use defaults on error

        # Load project config if exists
        project_config = self.workspace / self.PROJECT_CONFIG_FILE
        if project_config.exists():
            try:
                project_data = self._load_yaml(project_config)
                # Merge with user config
                config = self._merge_configs(config, project_data)
            except Exception:
                pass

        # Override with environment variables
        config = self._apply_env_overrides(config)

        self._config = config
        return config

    def save_user_config(self, config: CLIConfig):
        """Save configuration to user config file

        Args:
            config: Configuration to save
        """
        self.USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._save_yaml(self.USER_CONFIG_FILE, config.to_dict())

    def save_project_config(self, config: CLIConfig):
        """Save configuration to project config file

        Args:
            config: Configuration to save
        """
        project_dir = self.workspace / ".agentic-coder"
        project_dir.mkdir(parents=True, exist_ok=True)
        self._save_yaml(project_dir / "config.yaml", config.to_dict())

    def create_default_config(self, location: str = "user"):
        """Create default configuration file

        Args:
            location: 'user' or 'project'
        """
        config = CLIConfig()

        if location == "user":
            self.save_user_config(config)
            return self.USER_CONFIG_FILE
        else:
            self.save_project_config(config)
            return self.workspace / self.PROJECT_CONFIG_FILE

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load YAML file"""
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def _save_yaml(self, path: Path, data: Dict[str, Any]):
        """Save YAML file with comments"""
        header = """# Agentic Coder CLI Configuration
# See documentation for all options

"""
        with open(path, 'w', encoding='utf-8') as f:
            f.write(header)
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

    def _merge_configs(self, base: CLIConfig, override: Dict[str, Any]) -> CLIConfig:
        """Merge override dict into base config"""
        merged_dict = base.to_dict()

        # Deep merge
        for key, value in override.items():
            if key in merged_dict and isinstance(merged_dict[key], dict) and isinstance(value, dict):
                merged_dict[key].update(value)
            else:
                merged_dict[key] = value

        return CLIConfig.from_dict(merged_dict)

    def _apply_env_overrides(self, config: CLIConfig) -> CLIConfig:
        """Apply environment variable overrides from .env file and system environment.

        Environment variable priority (highest to lowest):
        1. System environment variables
        2. .env file values (loaded by __main__.py)
        3. Config file values
        4. Default values
        """
        # Environment variable mappings (env_var -> config attribute)
        env_mappings = {
            # Agentic Coder specific
            "AGENTIC_CODER_MODEL": "model",
            "AGENTIC_CODER_API_ENDPOINT": "api_endpoint",
            "AGENTIC_CODER_NETWORK_MODE": "network_mode",
            "AGENTIC_CODER_DEBUG": "debug",
            # Legacy TestCodeAgent (backward compatibility)
            "TESTCODEAGENT_MODEL": "model",
            "TESTCODEAGENT_API_ENDPOINT": "api_endpoint",
            "TESTCODEAGENT_NETWORK_MODE": "network_mode",
            "TESTCODEAGENT_DEBUG": "debug",
            # Standard LLM settings (from .env)
            "LLM_MODEL": "model",
            "LLM_ENDPOINT": "api_endpoint",
            "REASONING_MODEL": "model",  # Use reasoning model if available
            "VLLM_REASONING_ENDPOINT": "api_endpoint",  # Use reasoning endpoint
            # Network and debug
            "NETWORK_MODE": "network_mode",
            "LOG_LEVEL": "debug",  # DEBUG level enables debug mode
        }

        for env_var, attr in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                if attr == "debug":
                    # Handle both boolean and log level values
                    if value.upper() == "DEBUG":
                        value = True
                    else:
                        value = value.lower() in ("true", "1", "yes")
                setattr(config, attr, value)

        return config

    def get_history_path(self) -> Path:
        """Get history file path (expanded)"""
        config = self.get_config()
        return Path(config.history_file).expanduser()

    def get_session_dir(self) -> Path:
        """Get session directory path"""
        config = self.get_config()
        return self.workspace / config.session_dir
