"""Application configuration."""
import os
import platform
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List, Literal, Optional

# Get the project root directory path for .env file
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def get_default_workspace() -> str:
    """Get default workspace path based on OS.

    Returns:
        str: Default workspace path
        - Windows: C:\\Users\\<username>\\workspace
        - Linux/Mac: /home/user/workspace (or ~/workspace)
    """
    if platform.system() == "Windows":
        # Windows: use user's home directory
        return str(Path.home() / "workspace")
    else:
        # Linux/Mac
        return "/home/user/workspace"


DEFAULT_WORKSPACE = get_default_workspace()


def detect_model_type(model_name: str) -> str:
    """Auto-detect model type from model name.

    Args:
        model_name: Full model name (e.g., "deepseek-ai/DeepSeek-R1")

    Returns:
        Model type string: "deepseek", "qwen", "gpt-oss", "gpt", "claude", or "generic"
    """
    if not model_name:
        return "generic"

    name_lower = model_name.lower()

    if "deepseek" in name_lower:
        return "deepseek"
    elif "qwen" in name_lower:
        return "qwen"
    elif "gpt-oss" in name_lower:
        return "gpt-oss"  # GPT-OSS models (120B, 20B) - before generic "gpt" check
    elif "gpt" in name_lower or "openai" in name_lower:
        return "gpt"
    elif "claude" in name_lower or "anthropic" in name_lower:
        return "claude"
    elif "llama" in name_lower or "mistral" in name_lower or "mixtral" in name_lower:
        return "generic"  # Use generic for other open models
    else:
        return "generic"


class Settings(BaseSettings):
    """Application settings."""

    # =========================
    # LLM Model Configuration
    # =========================

    # Primary LLM endpoint (used as default for all tasks)
    llm_endpoint: str = "http://localhost:8001/v1"
    llm_model: str = "deepseek-ai/DeepSeek-R1"

    # Model type override (optional - auto-detected from model name if not set)
    # Options: "deepseek", "qwen", "gpt-oss", "gpt", "claude", "generic"
    model_type: Optional[str] = None

    # Optional: Task-specific endpoints (override llm_endpoint if set)
    vllm_reasoning_endpoint: Optional[str] = None
    vllm_coding_endpoint: Optional[str] = None

    # Optional: Task-specific models (override llm_model if set)
    reasoning_model: Optional[str] = None
    coding_model: Optional[str] = None

    # Optional: Task-specific model type overrides (for different model types per task)
    reasoning_model_type: Optional[str] = None
    coding_model_type: Optional[str] = None

    # GPT-OSS specific settings
    gpt_oss_reasoning_effort: str = "low"  # low, medium, high - default is low per official docs

    @property
    def get_reasoning_endpoint(self) -> str:
        """Get endpoint for reasoning tasks."""
        return self.vllm_reasoning_endpoint or self.llm_endpoint

    @property
    def get_coding_endpoint(self) -> str:
        """Get endpoint for coding tasks."""
        return self.vllm_coding_endpoint or self.llm_endpoint

    @property
    def get_reasoning_model(self) -> str:
        """Get model for reasoning tasks."""
        return self.reasoning_model or self.llm_model

    @property
    def get_coding_model(self) -> str:
        """Get model for coding tasks."""
        return self.coding_model or self.llm_model

    @property
    def get_reasoning_model_type(self) -> str:
        """Get model type for reasoning tasks (auto-detected from model name)."""
        # Priority: task-specific override > global override > auto-detect
        if self.reasoning_model_type:
            return self.reasoning_model_type
        if self.model_type:
            return self.model_type
        return detect_model_type(self.get_reasoning_model)

    @property
    def get_coding_model_type(self) -> str:
        """Get model type for coding tasks (auto-detected from model name)."""
        # Priority: task-specific override > global override > auto-detect
        if self.coding_model_type:
            return self.coding_model_type
        if self.model_type:
            return self.model_type
        return detect_model_type(self.get_coding_model)

    # =========================
    # Agent Framework Selection
    # =========================
    # Options: "microsoft", "langchain", "deepagent"
    agent_framework: Literal["microsoft", "langchain", "deepagent"] = "microsoft"

    # Workflow Configuration
    max_review_iterations: int = 3  # Maximum code review/fix iterations

    # Coder batch size - for parallel file generation display
    # Higher values for powerful GPUs (H100: 10-15, A100: 8-10, RTX 4090: 5-8)
    coder_batch_size: int = 10  # Default optimized for H100

    # =========================
    # Workspace Configuration
    # =========================
    # Default workspace path (auto-detected based on OS if not set)
    default_workspace: str = DEFAULT_WORKSPACE

    # =========================
    # API Configuration
    # =========================
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Logging
    log_level: str = "INFO"

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins to list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = str(ENV_FILE)
        case_sensitive = False


# Create settings instance
settings = Settings()

# Log loaded configuration at startup (helps debug .env loading issues)
import logging
_logger = logging.getLogger(__name__)
_logger.info(f"📁 Config loaded from: {ENV_FILE} (exists: {ENV_FILE.exists()})")
_logger.info(f"🔧 Coding endpoint: {settings.get_coding_endpoint}")
_logger.info(f"🔧 Reasoning endpoint: {settings.get_reasoning_endpoint}")
