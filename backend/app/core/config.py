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

    # Optional: Multiple endpoints for load balancing (comma-separated)
    # Example: "http://localhost:8001/v1,http://localhost:8002/v1"
    # If set, load balances across all endpoints using round-robin
    vllm_endpoints: Optional[str] = None

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

    @property
    def get_vllm_endpoints_list(self) -> List[str]:
        """Get list of vLLM endpoints for load balancing.

        Returns:
            List of endpoint URLs. If vllm_endpoints is not set, returns list with single llm_endpoint.
        """
        if self.vllm_endpoints:
            return [endpoint.strip() for endpoint in self.vllm_endpoints.split(",")]
        return [self.llm_endpoint]

    # =========================
    # Agent Framework Selection
    # =========================
    # Options: "microsoft", "langchain", "deepagent"
    agent_framework: Literal["microsoft", "langchain", "deepagent"] = "microsoft"

    # Workflow Configuration
    max_review_iterations: int = 1  # Maximum code review/fix iterations (default: 1 for speed)

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

    # =========================
    # Network Mode Configuration (Phase 2)
    # =========================
    # Controls which tools are available based on network access
    # Options: online (all tools) | offline (local tools only)
    network_mode: str = "online"

    # =========================
    # Agent Tools Configuration
    # =========================
    # ChromaDB Path for Code Search Tool
    chroma_db_path: str = "./chroma_db"

    # Tavily API Key for Web Search (optional)
    tavily_api_key: Optional[str] = None

    # =========================
    # Sandbox Configuration (Phase 4)
    # =========================
    # Docker-based isolated code execution
    sandbox_image: str = "ghcr.io/agent-infra/sandbox:latest"
    sandbox_host: str = "localhost"
    sandbox_port: int = 8080
    sandbox_timeout: int = 60
    sandbox_memory: str = "1g"
    sandbox_cpu: float = 2.0

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert comma-separated CORS origins to list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    class Config:
        env_file = str(ENV_FILE)
        case_sensitive = False


# Create settings instance
settings = Settings()

# Logger for configuration module
import logging
_config_logger = logging.getLogger(__name__)


def log_configuration():
    """Log loaded configuration at startup.

    Call this function after logging is configured to see startup info.
    """
    _config_logger.info("=" * 60)
    _config_logger.info("CONFIGURATION LOADED")
    _config_logger.info("=" * 60)
    _config_logger.info(f".env file path: {ENV_FILE}")
    _config_logger.info(f".env file exists: {ENV_FILE.exists()}")
    _config_logger.info("-" * 60)
    _config_logger.info("LLM Settings:")
    _config_logger.info(f"   LLM_ENDPOINT: {settings.llm_endpoint}")
    _config_logger.info(f"   LLM_MODEL: {settings.llm_model}")
    _config_logger.info(f"   MODEL_TYPE: {settings.model_type or 'auto-detect'}")

    # Load Balancing Configuration
    endpoints = settings.get_vllm_endpoints_list
    if len(endpoints) > 1:
        _config_logger.info(f"   LOAD BALANCING: Enabled ({len(endpoints)} endpoints)")
        for i, endpoint in enumerate(endpoints):
            _config_logger.info(f"      [{i+1}] {endpoint}")
    else:
        _config_logger.info(f"   LOAD BALANCING: Disabled (single endpoint)")
        if settings.vllm_reasoning_endpoint and settings.vllm_coding_endpoint:
            _config_logger.info(f"   REASONING_ENDPOINT: {settings.get_reasoning_endpoint}")
            _config_logger.info(f"   CODING_ENDPOINT: {settings.get_coding_endpoint}")
            _config_logger.info(f"   REASONING_MODEL: {settings.get_reasoning_model}")
            _config_logger.info(f"   CODING_MODEL: {settings.get_coding_model}")
    _config_logger.info("-" * 60)
    _config_logger.info("Workflow Settings:")
    _config_logger.info(f"   AGENT_FRAMEWORK: {settings.agent_framework}")
    _config_logger.info(f"   MAX_PARALLEL_AGENTS: {settings.max_parallel_agents}")
    _config_logger.info(f"   ENABLE_PARALLEL_CODING: {settings.enable_parallel_coding}")
    _config_logger.info(f"   CODER_BATCH_SIZE: {settings.coder_batch_size}")
    _config_logger.info(f"   MAX_REVIEW_ITERATIONS: {settings.max_review_iterations}")
    _config_logger.info("-" * 60)
    _config_logger.info("Workspace Settings:")
    _config_logger.info(f"   DEFAULT_WORKSPACE: {settings.default_workspace}")
    _config_logger.info("-" * 60)
    _config_logger.info("Server Settings:")
    _config_logger.info(f"   API_HOST: {settings.api_host}")
    _config_logger.info(f"   API_PORT: {settings.api_port}")
    _config_logger.info(f"   CORS_ORIGINS: {settings.cors_origins}")
    _config_logger.info(f"   LOG_LEVEL: {settings.log_level}")
    _config_logger.info("-" * 60)
    _config_logger.info("Network & Tools Settings:")
    _config_logger.info(f"   NETWORK_MODE: {settings.network_mode}")
    _config_logger.info(f"   CHROMA_DB_PATH: {settings.chroma_db_path}")
    _config_logger.info("-" * 60)
    _config_logger.info("Sandbox Settings:")
    _config_logger.info(f"   SANDBOX_IMAGE: {settings.sandbox_image}")
    _config_logger.info(f"   SANDBOX_HOST: {settings.sandbox_host}")
    _config_logger.info(f"   SANDBOX_PORT: {settings.sandbox_port}")
    _config_logger.info(f"   SANDBOX_TIMEOUT: {settings.sandbox_timeout}")
    _config_logger.info("=" * 60)
