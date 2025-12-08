"""vLLM client for interacting with OpenAI-compatible endpoints."""
import logging
from typing import AsyncGenerator, Optional, Dict, Any
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class VLLMClient:
    """Client for vLLM OpenAI-compatible API."""

    def __init__(self, base_url: str, model_name: str):
        """Initialize vLLM client.

        Args:
            base_url: Base URL for vLLM endpoint (e.g., http://localhost:8001/v1)
            model_name: Name of the model to use
        """
        self.base_url = base_url
        self.model_name = model_name
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key="dummy-key"  # vLLM doesn't require real API key
        )
        logger.info(f"Initialized vLLM client for {model_name} at {base_url}")

    async def chat_completion(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        **kwargs
    ) -> Any:
        """Create a chat completion.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional arguments to pass to the API

        Returns:
            Chat completion response or async generator if streaming
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs
            )
            return response
        except Exception as e:
            logger.error(f"Error calling vLLM API: {e}")
            raise

    async def stream_chat_completion(
        self,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion.

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional arguments

        Yields:
            Chunks of generated text
        """
        try:
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error streaming from vLLM API: {e}")
            raise


class VLLMRouter:
    """Router for selecting appropriate vLLM model based on task type."""

    def __init__(self):
        """Initialize vLLM router with reasoning and coding clients."""
        self.reasoning_client = VLLMClient(
            base_url=settings.vllm_reasoning_endpoint,
            model_name=settings.reasoning_model
        )
        self.coding_client = VLLMClient(
            base_url=settings.vllm_coding_endpoint,
            model_name=settings.coding_model
        )
        logger.info("VLLMRouter initialized with reasoning and coding clients")

    def get_client(self, task_type: str = "coding") -> VLLMClient:
        """Get appropriate client based on task type.

        Args:
            task_type: Type of task ('reasoning' or 'coding')

        Returns:
            Appropriate VLLMClient instance
        """
        if task_type.lower() == "reasoning":
            return self.reasoning_client
        return self.coding_client


# Global router instance
vllm_router = VLLMRouter()
