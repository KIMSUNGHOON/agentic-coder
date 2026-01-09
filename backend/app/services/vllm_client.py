"""vLLM client for interacting with OpenAI-compatible endpoints."""
import logging
import threading
from typing import AsyncGenerator, Optional, Dict, Any, List
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

    async def chat_completion_with_tools(
        self,
        messages: list[Dict[str, str]],
        tools: list[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tool_choice: str = "auto",
        **kwargs
    ) -> Any:
        """Create a chat completion with function/tool calling support.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: List of tool definitions in OpenAI format
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tool_choice: How to select tools ('auto', 'required', 'none')
            **kwargs: Additional arguments to pass to the API

        Returns:
            Chat completion response with tool_calls if LLM wants to call tools
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,  # Tool calling doesn't support streaming
                **kwargs
            )
            return response
        except Exception as e:
            logger.error(f"Error calling vLLM API with tools: {e}")
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
    """Router for vLLM clients with load balancing support.

    Supports two modes:
    1. Load Balancing Mode: Multiple endpoints for the same model (round-robin)
    2. Task-Based Mode: Different endpoints for reasoning vs coding tasks
    """

    def __init__(self):
        """Initialize vLLM router with load balancing or task-based routing."""
        self._lock = threading.Lock()
        self._round_robin_index = 0

        # Check if load balancing mode is enabled (multiple endpoints configured)
        endpoints = settings.get_vllm_endpoints_list

        if len(endpoints) > 1:
            # Load Balancing Mode: Multiple endpoints for same model
            self.mode = "load_balancing"
            self.clients: List[VLLMClient] = []

            for i, endpoint in enumerate(endpoints):
                client = VLLMClient(
                    base_url=endpoint,
                    model_name=settings.llm_model
                )
                self.clients.append(client)

            logger.info(f"🔀 VLLMRouter initialized in LOAD BALANCING mode")
            logger.info(f"   📊 {len(self.clients)} endpoints configured:")
            for i, endpoint in enumerate(endpoints):
                logger.info(f"      [{i+1}] {endpoint}")
            logger.info(f"   🔄 Strategy: Round-robin across all endpoints")

        elif settings.vllm_reasoning_endpoint and settings.vllm_coding_endpoint:
            # Task-Based Mode: Separate endpoints for reasoning and coding
            self.mode = "task_based"
            self.reasoning_client = VLLMClient(
                base_url=settings.vllm_reasoning_endpoint,
                model_name=settings.reasoning_model or settings.llm_model
            )
            self.coding_client = VLLMClient(
                base_url=settings.vllm_coding_endpoint,
                model_name=settings.coding_model or settings.llm_model
            )
            logger.info(f"🎯 VLLMRouter initialized in TASK-BASED mode")
            logger.info(f"   🧠 Reasoning: {settings.vllm_reasoning_endpoint}")
            logger.info(f"   💻 Coding: {settings.vllm_coding_endpoint}")

        else:
            # Single Endpoint Mode: Use primary endpoint only
            self.mode = "single"
            self.primary_client = VLLMClient(
                base_url=settings.llm_endpoint,
                model_name=settings.llm_model
            )
            logger.info(f"📍 VLLMRouter initialized in SINGLE ENDPOINT mode")
            logger.info(f"   🔗 Endpoint: {settings.llm_endpoint}")

    def get_client(self, task_type: str = "coding") -> VLLMClient:
        """Get appropriate vLLM client based on routing mode.

        Args:
            task_type: Type of task ('reasoning' or 'coding') - only used in task-based mode

        Returns:
            VLLMClient instance (load balanced or task-specific)
        """
        if self.mode == "load_balancing":
            # Round-robin load balancing across all clients
            with self._lock:
                client = self.clients[self._round_robin_index]
                self._round_robin_index = (self._round_robin_index + 1) % len(self.clients)
                return client

        elif self.mode == "task_based":
            # Task-specific routing
            if task_type.lower() == "reasoning":
                return self.reasoning_client
            return self.coding_client

        else:
            # Single endpoint
            return self.primary_client

    def get_load_balancing_stats(self) -> Dict[str, Any]:
        """Get load balancing statistics.

        Returns:
            Dictionary with routing mode, endpoint count, and current index
        """
        stats = {
            "mode": self.mode,
            "endpoint_count": 1,
            "current_index": 0
        }

        if self.mode == "load_balancing":
            stats["endpoint_count"] = len(self.clients)
            stats["current_index"] = self._round_robin_index
            stats["endpoints"] = [client.base_url for client in self.clients]

        elif self.mode == "task_based":
            stats["endpoint_count"] = 2
            stats["reasoning_endpoint"] = self.reasoning_client.base_url
            stats["coding_endpoint"] = self.coding_client.base_url

        else:
            stats["endpoint"] = self.primary_client.base_url

        return stats


# Global router instance
vllm_router = VLLMRouter()
