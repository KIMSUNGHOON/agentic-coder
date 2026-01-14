"""Configuration Loader for Agentic 2.0

Loads and validates configuration from YAML files.
Supports environment variable overrides and development/production profiles.
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class EndpointConfig:
    """LLM endpoint configuration"""

    url: str
    name: str
    timeout: int = 120


@dataclass
class LLMConfig:
    """LLM configuration"""

    model_name: str
    endpoints: List[Dict[str, Any]]
    health_check: Dict[str, Any]
    retry: Dict[str, int]
    parameters: Dict[str, float]


@dataclass
class WorkflowConfig:
    """Workflow configuration"""

    max_iterations: int
    timeout_seconds: int
    sub_agents: Dict[str, Any]


@dataclass
class ToolSafetyConfig:
    """Tool safety configuration"""

    enabled: bool
    command_allowlist: List[str]
    command_denylist: List[str]
    protected_files: List[str]
    protected_patterns: List[str]


@dataclass
class ToolConfig:
    """Tool configuration"""

    safety: ToolSafetyConfig
    network: Dict[str, Any]


@dataclass
class PersistenceConfig:
    """Persistence configuration"""

    backend: str
    database_url: str
    checkpoint: Dict[str, Any]
    thread: Dict[str, Any]


@dataclass
class LoggingConfig:
    """Logging configuration"""

    level: str
    format: str
    file: str
    rotation: str
    max_size_mb: int
    log_agent_decisions: bool
    log_tool_calls: bool
    log_llm_requests: bool
    log_state_changes: bool


@dataclass
class WorkspaceConfig:
    """Workspace configuration"""

    default_path: str
    isolation: bool
    cleanup: bool
    git: Dict[str, bool]


@dataclass
class PerformanceConfig:
    """Performance configuration"""

    parallel_tool_calls: bool
    max_parallel_tools: int
    tool_timeout_seconds: int
    cache: Dict[str, Any]


@dataclass
class DevelopmentConfig:
    """Development configuration"""

    debug_mode: bool
    mock_llm: bool
    save_prompts: bool
    prompt_dir: str


@dataclass
class Config:
    """Complete application configuration"""

    mode: str
    llm: LLMConfig
    workflows: WorkflowConfig
    tools: ToolConfig
    persistence: PersistenceConfig
    logging: LoggingConfig
    workspace: WorkspaceConfig
    performance: PerformanceConfig
    development: DevelopmentConfig

    @classmethod
    def load(cls, config_path: str = "config/config.yaml") -> "Config":
        """Load configuration from YAML file

        Args:
            config_path: Path to configuration file

        Returns:
            Config object with all settings

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Create it by copying config/config.yaml.example"
            )

        with open(config_file, "r") as f:
            data = yaml.safe_load(f)

        # Parse LLM config
        llm_data = data["llm"]
        llm_config = LLMConfig(
            model_name=llm_data["model_name"],
            endpoints=llm_data["endpoints"],
            health_check=llm_data["health_check"],
            retry=llm_data["retry"],
            parameters=llm_data["parameters"],
        )

        # Parse workflow config
        workflow_data = data["workflows"]
        workflows_config = WorkflowConfig(
            max_iterations=workflow_data["max_iterations"],
            timeout_seconds=workflow_data["timeout_seconds"],
            sub_agents=workflow_data["sub_agents"],
        )

        # Parse tool config
        tool_data = data["tools"]
        safety_data = tool_data["safety"]
        tool_safety = ToolSafetyConfig(
            enabled=safety_data["enabled"],
            command_allowlist=safety_data["command_allowlist"],
            command_denylist=safety_data["command_denylist"],
            protected_files=safety_data["protected_files"],
            protected_patterns=safety_data["protected_patterns"],
        )
        tools_config = ToolConfig(
            safety=tool_safety, network=tool_data["network"]
        )

        # Parse persistence config
        persistence_data = data["persistence"]
        persistence_config = PersistenceConfig(
            backend=persistence_data["backend"],
            database_url=persistence_data["database_url"],
            checkpoint=persistence_data["checkpoint"],
            thread=persistence_data["thread"],
        )

        # Parse logging config
        logging_data = data["logging"]
        logging_config = LoggingConfig(
            level=logging_data["level"],
            format=logging_data["format"],
            file=logging_data["file"],
            rotation=logging_data["rotation"],
            max_size_mb=logging_data["max_size_mb"],
            log_agent_decisions=logging_data["log_agent_decisions"],
            log_tool_calls=logging_data["log_tool_calls"],
            log_llm_requests=logging_data["log_llm_requests"],
            log_state_changes=logging_data["log_state_changes"],
        )

        # Parse workspace config
        workspace_data = data["workspace"]
        workspace_config = WorkspaceConfig(
            default_path=workspace_data["default_path"],
            isolation=workspace_data["isolation"],
            cleanup=workspace_data["cleanup"],
            git=workspace_data["git"],
        )

        # Parse performance config
        performance_data = data["performance"]
        performance_config = PerformanceConfig(
            parallel_tool_calls=performance_data["parallel_tool_calls"],
            max_parallel_tools=performance_data["max_parallel_tools"],
            tool_timeout_seconds=performance_data["tool_timeout_seconds"],
            cache=performance_data["cache"],
        )

        # Parse development config
        development_data = data["development"]
        development_config = DevelopmentConfig(
            debug_mode=development_data["debug_mode"],
            mock_llm=development_data["mock_llm"],
            save_prompts=development_data["save_prompts"],
            prompt_dir=development_data["prompt_dir"],
        )

        return cls(
            mode=data["mode"],
            llm=llm_config,
            workflows=workflows_config,
            tools=tools_config,
            persistence=persistence_config,
            logging=logging_config,
            workspace=workspace_config,
            performance=performance_config,
            development=development_config,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary

        Returns:
            Dictionary representation of configuration
        """
        return {
            "mode": self.mode,
            "llm": {
                "model_name": self.llm.model_name,
                "endpoints": self.llm.endpoints,
                "health_check": self.llm.health_check,
                "retry": self.llm.retry,
                "parameters": self.llm.parameters,
            },
            "workflows": {
                "max_iterations": self.workflows.max_iterations,
                "timeout_seconds": self.workflows.timeout_seconds,
                "sub_agents": self.workflows.sub_agents,
            },
            "tools": {
                "safety": {
                    "enabled": self.tools.safety.enabled,
                    "command_allowlist": self.tools.safety.command_allowlist,
                    "command_denylist": self.tools.safety.command_denylist,
                    "protected_files": self.tools.safety.protected_files,
                    "protected_patterns": self.tools.safety.protected_patterns,
                },
                "network": self.tools.network,
            },
            "persistence": {
                "backend": self.persistence.backend,
                "database_url": self.persistence.database_url,
                "checkpoint": self.persistence.checkpoint,
                "thread": self.persistence.thread,
            },
            "logging": {
                "level": self.logging.level,
                "format": self.logging.format,
                "file": self.logging.file,
                "rotation": self.logging.rotation,
                "max_size_mb": self.logging.max_size_mb,
                "log_agent_decisions": self.logging.log_agent_decisions,
                "log_tool_calls": self.logging.log_tool_calls,
                "log_llm_requests": self.logging.log_llm_requests,
                "log_state_changes": self.logging.log_state_changes,
            },
            "workspace": {
                "default_path": self.workspace.default_path,
                "isolation": self.workspace.isolation,
                "cleanup": self.workspace.cleanup,
                "git": self.workspace.git,
            },
            "performance": {
                "parallel_tool_calls": self.performance.parallel_tool_calls,
                "max_parallel_tools": self.performance.max_parallel_tools,
                "tool_timeout_seconds": self.performance.tool_timeout_seconds,
                "cache": self.performance.cache,
            },
            "development": {
                "debug_mode": self.development.debug_mode,
                "mock_llm": self.development.mock_llm,
                "save_prompts": self.development.save_prompts,
                "prompt_dir": self.development.prompt_dir,
            },
        }

    def validate(self) -> List[str]:
        """Validate configuration

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check mode
        if self.mode not in ["on-premise"]:
            errors.append(f"Invalid mode: {self.mode}. Must be 'on-premise'")

        # Check LLM endpoints
        if not self.llm.endpoints:
            errors.append("At least one LLM endpoint must be configured")

        # Check workflow limits
        if self.workflows.max_iterations < 1:
            errors.append("max_iterations must be >= 1")

        if self.workflows.timeout_seconds < 60:
            errors.append("timeout_seconds must be >= 60")

        # Check persistence backend
        if self.persistence.backend not in ["sqlite", "postgresql"]:
            errors.append(
                f"Invalid persistence backend: {self.persistence.backend}"
            )

        # Check logging level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.logging.level not in valid_levels:
            errors.append(
                f"Invalid logging level: {self.logging.level}. "
                f"Must be one of {valid_levels}"
            )

        return errors


def load_config(config_path: str = "config/config.yaml") -> Config:
    """Convenience function to load and validate configuration

    Args:
        config_path: Path to configuration file

    Returns:
        Validated Config object

    Raises:
        ValueError: If configuration is invalid
    """
    config = Config.load(config_path)

    # Validate
    errors = config.validate()
    if errors:
        raise ValueError(
            f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return config
