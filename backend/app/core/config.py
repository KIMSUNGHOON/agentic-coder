"""Application configuration."""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings."""

    # vLLM Endpoints
    vllm_reasoning_endpoint: str = "http://localhost:8001/v1"
    vllm_coding_endpoint: str = "http://localhost:8002/v1"

    # Model names
    reasoning_model: str = "deepseek-ai/DeepSeek-R1"
    coding_model: str = "Qwen/Qwen3-8B-Coder"

    # API Configuration
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
        env_file = ".env"
        case_sensitive = False


settings = Settings()
