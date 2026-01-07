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

    Priority:
    1. Environment variable DEFAULT_WORKSPACE (if set)
    2. User's home directory + workspace

    Returns:
        str: Default workspace path
        - Windows: C:\\Users\\<username>\\workspace
        - Linux/Mac: /home/<username>/workspace
    """
    # Priority 1: Check environment variable
    env_workspace = os.environ.get("DEFAULT_WORKSPACE")
    if env_workspace:
        return env_workspace

    # Priority 2: Use user's home directory (cross-platform)
    return str(Path.home() / "workspace")


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

    # Max parallel coding agents
    # H100 + vLLM: 25 (continuous batching)
    # A100 + vLLM: 15
    # RTX 4090 + vLLM: 8
    # RTX 3090 + Ollama: 1-2 (sequential processing recommended)
    max_parallel_agents: int = 2  # Default for Ollama/single GPU

    # Enable parallel coding (set to False for sequential processing)
    enable_parallel_coding: bool = True

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

# Print loaded configuration at startup (before logging is configured)
print("=" * 60)
print("📁 CONFIGURATION LOADED")
print("=" * 60)
print(f"📂 .env file path: {ENV_FILE}")
print(f"📂 .env file exists: {ENV_FILE.exists()}")
print("-" * 60)
print("🔧 LLM Settings:")
print(f"   LLM_ENDPOINT: {settings.llm_endpoint}")
print(f"   LLM_MODEL: {settings.llm_model}")
print(f"   MODEL_TYPE: {settings.model_type or 'auto-detect'}")
print(f"   REASONING_ENDPOINT: {settings.get_reasoning_endpoint}")
print(f"   CODING_ENDPOINT: {settings.get_coding_endpoint}")
print(f"   REASONING_MODEL: {settings.get_reasoning_model}")
print(f"   CODING_MODEL: {settings.get_coding_model}")
print("-" * 60)
print("⚙️ Workflow Settings:")
print(f"   AGENT_FRAMEWORK: {settings.agent_framework}")
print(f"   MAX_PARALLEL_AGENTS: {settings.max_parallel_agents}")
print(f"   ENABLE_PARALLEL_CODING: {settings.enable_parallel_coding}")
print(f"   CODER_BATCH_SIZE: {settings.coder_batch_size}")
print(f"   MAX_REVIEW_ITERATIONS: {settings.max_review_iterations}")
print("-" * 60)
print("📂 Workspace Settings:")
print(f"   DEFAULT_WORKSPACE: {settings.default_workspace}")
print("-" * 60)
print("🌐 Server Settings:")
print(f"   API_HOST: {settings.api_host}")
print(f"   API_PORT: {settings.api_port}")
print(f"   CORS_ORIGINS: {settings.cors_origins}")
print(f"   LOG_LEVEL: {settings.log_level}")
print("=" * 60)
