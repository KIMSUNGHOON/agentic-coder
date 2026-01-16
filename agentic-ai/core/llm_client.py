"""DualEndpointLLMClient - LLM client with automatic failover

This module implements a production-ready LLM client that supports:
- Dual endpoints (active-active or primary/secondary)
- Automatic health checks every 30s
- Exponential backoff retry (2s, 4s, 8s, 16s)
- Automatic failover on timeout/error
- Per-endpoint status tracking

Key Features:
✅ On-premise only - No external API dependencies
✅ vLLM OpenAI-compatible endpoint support
✅ Round-robin load balancing across healthy endpoints
✅ Detailed logging for debugging
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

try:
    from openai import AsyncOpenAI
    from openai.types.chat import ChatCompletion
except ImportError:
    raise ImportError(
        "OpenAI package not installed. "
        "Install with: pip install openai>=1.0.0"
    )

logger = logging.getLogger(__name__)


@dataclass
class EndpointConfig:
    """Configuration for a single LLM endpoint"""
    url: str
    name: str
    timeout: int = 120


class EndpointHealth:
    """Tracks health status of an endpoint"""

    def __init__(self, name: str):
        self.name = name
        self.is_healthy = True
        self.last_success: Optional[float] = None
        self.last_failure: Optional[float] = None
        self.last_health_check: float = 0.0
        self.consecutive_failures = 0
        self.total_requests = 0
        self.total_failures = 0

    def record_success(self):
        """Record successful request"""
        self.is_healthy = True
        self.last_success = time.time()
        self.consecutive_failures = 0
        self.total_requests += 1
        logger.debug(f"✅ Endpoint {self.name}: Request successful")

    def record_failure(self):
        """Record failed request"""
        self.last_failure = time.time()
        self.consecutive_failures += 1
        self.total_requests += 1
        self.total_failures += 1

        # Mark unhealthy after 3 consecutive failures
        if self.consecutive_failures >= 3:
            self.is_healthy = False
            logger.warning(
                f"⚠️  Endpoint {self.name}: Marked unhealthy "
                f"({self.consecutive_failures} consecutive failures)"
            )
        else:
            logger.debug(
                f"⚠️  Endpoint {self.name}: Failure {self.consecutive_failures}/3"
            )

    def record_health_check(self, success: bool):
        """Record health check result"""
        self.last_health_check = time.time()
        if success:
            if not self.is_healthy:
                logger.info(f"✅ Endpoint {self.name}: Recovered (health check passed)")
            self.is_healthy = True
            self.consecutive_failures = 0
        else:
            logger.warning(f"⚠️  Endpoint {self.name}: Health check failed")

    def get_stats(self) -> Dict[str, Any]:
        """Get endpoint statistics"""
        return {
            "name": self.name,
            "is_healthy": self.is_healthy,
            "consecutive_failures": self.consecutive_failures,
            "total_requests": self.total_requests,
            "total_failures": self.total_failures,
            "success_rate": (
                (self.total_requests - self.total_failures) / self.total_requests
                if self.total_requests > 0
                else 0.0
            ),
            "last_success": (
                datetime.fromtimestamp(self.last_success).isoformat()
                if self.last_success
                else None
            ),
            "last_failure": (
                datetime.fromtimestamp(self.last_failure).isoformat()
                if self.last_failure
                else None
            ),
        }


class DualEndpointLLMClient:
    """LLM client with dual endpoint support and automatic failover

    Features:
    - Active-active load balancing OR primary/secondary failover
    - Health checks every 30s
    - Exponential backoff retry (2s, 4s, 8s, 16s)
    - Automatic failover on timeout/error
    - Per-endpoint status tracking

    Example:
        >>> endpoints = [
        ...     EndpointConfig(url="http://localhost:8001/v1", name="primary"),
        ...     EndpointConfig(url="http://localhost:8002/v1", name="secondary")
        ... ]
        >>> client = DualEndpointLLMClient(endpoints)
        >>> response = await client.chat_completion([
        ...     {"role": "user", "content": "Hello"}
        ... ])
    """

    def __init__(
        self,
        endpoints: List[EndpointConfig],
        model_name: str = "gpt-oss-120b",
        health_check_interval: int = 30,
        max_retries: int = 4,
        backoff_base: int = 2,
        api_key: str = "not-needed",  # vLLM doesn't require API key
    ):
        """Initialize DualEndpointLLMClient

        Args:
            endpoints: List of endpoint configurations
            model_name: Model name to use (default: gpt-oss-120b)
            health_check_interval: Seconds between health checks (default: 30)
            max_retries: Maximum retry attempts (default: 4)
            backoff_base: Exponential backoff base (default: 2)
            api_key: API key for endpoints (default: "not-needed" for vLLM)
        """
        if not endpoints:
            raise ValueError("At least one endpoint must be provided")

        self.endpoints = endpoints
        self.model_name = model_name
        self.health_check_interval = health_check_interval
        self.max_retries = max_retries
        self.backoff_base = backoff_base

        # Health tracking
        self.health = {ep.name: EndpointHealth(ep.name) for ep in endpoints}

        # Round-robin index
        self.current_index = 0
        self._index_lock = asyncio.Lock()

        # Create OpenAI clients for each endpoint
        self.clients = {
            ep.name: AsyncOpenAI(
                base_url=ep.url,
                api_key=api_key,
                timeout=ep.timeout,
            )
            for ep in endpoints
        }

        logger.info(
            f"🚀 DualEndpointLLMClient initialized with {len(endpoints)} endpoints:"
        )
        for ep in endpoints:
            logger.info(f"   - {ep.name}: {ep.url}")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_tokens: int = 4096,
        **kwargs,
    ) -> ChatCompletion:
        """Make chat completion request with automatic failover

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            top_p: Nucleus sampling parameter (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters passed to OpenAI API

        Returns:
            ChatCompletion object from OpenAI

        Raises:
            Exception: If all retry attempts fail on all endpoints
        """
        request_id = f"req_{int(time.time() * 1000)}"
        logger.info(f"📤 Starting chat completion request [{request_id}]")
        logger.info(f"   Messages: {len(messages)}, Temp: {temperature}")

        # Log full request (CRITICAL for debugging)
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            content_preview = content[:500] + "..." if len(content) > 500 else content
            logger.info(f"   [{i+1}] {role}: {content_preview}")

        last_exception = None

        for attempt in range(self.max_retries):
            endpoint = await self._get_next_healthy_endpoint()

            if not endpoint:
                backoff = self.backoff_base**attempt
                logger.warning(
                    f"⚠️  No healthy endpoints available (attempt {attempt + 1}/{self.max_retries}). "
                    f"Retrying in {backoff}s..."
                )
                await asyncio.sleep(backoff)
                continue

            try:
                logger.info(
                    f"🎯 [{request_id}] Attempting on {endpoint.name} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

                start_time = time.time()

                # Make request
                client = self.clients[endpoint.name]
                response = await client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                elapsed = time.time() - start_time

                # Record success
                self.health[endpoint.name].record_success()

                # Extract response content
                response_content = response.choices[0].message.content if response.choices else "No content"
                response_preview = response_content[:500] + "..." if len(response_content) > 500 else response_content

                logger.info(
                    f"✅ [{request_id}] Success on {endpoint.name} "
                    f"({elapsed:.2f}s, {response.usage.total_tokens} tokens)"
                )
                logger.info(f"📥 Response: {response_preview}")

                return response

            except (TimeoutError, asyncio.TimeoutError) as e:
                last_exception = e
                logger.warning(
                    f"⏱️  [{request_id}] Timeout on {endpoint.name}: {e}"
                )
                self.health[endpoint.name].record_failure()

            except ConnectionError as e:
                last_exception = e
                logger.warning(
                    f"🔌 [{request_id}] Connection error on {endpoint.name}: {e}"
                )
                self.health[endpoint.name].record_failure()

            except Exception as e:
                last_exception = e
                logger.error(
                    f"❌ [{request_id}] Error on {endpoint.name}: {e}",
                    exc_info=True
                )
                self.health[endpoint.name].record_failure()

            # Exponential backoff before retry
            if attempt < self.max_retries - 1:
                backoff = self.backoff_base**attempt
                logger.info(f"⏳ Backing off for {backoff}s before retry...")
                await asyncio.sleep(backoff)

        # All attempts failed
        error_msg = (
            f"❌ All {self.max_retries} attempts failed on all endpoints. "
            f"Last error: {last_exception}"
        )
        logger.error(error_msg)
        raise Exception(error_msg)

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        top_p: float = 0.95,
        max_tokens: int = 4096,
        **kwargs,
    ):
        """Make streaming chat completion request with automatic failover

        Yields:
            str: Chunks of generated text as they arrive

        This method enables real-time streaming of LLM responses, which is critical for:
        1. User experience: See output as it's generated
        2. vLLM optimization: Continuous batching works better with streaming
        3. Debugging: Understand what LLM is doing in real-time

        Example:
            >>> async for chunk in client.chat_completion_stream(messages):
            ...     print(chunk, end="", flush=True)
        """
        request_id = f"req_{int(time.time() * 1000)}"
        logger.info(f"📤 Starting STREAMING chat completion [{request_id}]")
        logger.info(f"   Messages: {len(messages)}, Temp: {temperature}")

        # Log full request (CRITICAL for debugging)
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            content_preview = content[:500] + "..." if len(content) > 500 else content
            logger.info(f"   [{i+1}] {role}: {content_preview}")

        last_exception = None

        for attempt in range(self.max_retries):
            endpoint = await self._get_next_healthy_endpoint()

            if not endpoint:
                backoff = self.backoff_base**attempt
                logger.warning(
                    f"⚠️  No healthy endpoints available (attempt {attempt + 1}/{self.max_retries}). "
                    f"Retrying in {backoff}s..."
                )
                await asyncio.sleep(backoff)
                continue

            try:
                logger.info(
                    f"🎯 [{request_id}] Streaming from {endpoint.name} "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )

                start_time = time.time()

                # Make STREAMING request
                client = self.clients[endpoint.name]
                stream = await client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=temperature,
                    top_p=top_p,
                    max_tokens=max_tokens,
                    stream=True,  # Enable streaming!
                    **kwargs,
                )

                # Stream chunks
                full_response = ""
                async for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta.content:
                            full_response += delta.content
                            yield delta.content  # Yield each chunk as it arrives

                # Log completion
                elapsed = time.time() - start_time
                logger.info(
                    f"✅ [{request_id}] Streaming completed in {elapsed:.2f}s "
                    f"({len(full_response)} chars)"
                )
                self.health[endpoint.name].record_success()

                return  # Success! Exit the retry loop

            except asyncio.TimeoutError:
                last_exception = Exception(f"Timeout after {endpoint.timeout}s")
                logger.error(
                    f"⏱️  [{request_id}] Timeout on {endpoint.name} after {endpoint.timeout}s"
                )
                self.health[endpoint.name].record_failure()

            except Exception as e:
                last_exception = e
                logger.error(
                    f"❌ [{request_id}] Stream error on {endpoint.name}: {e}",
                    exc_info=True
                )
                self.health[endpoint.name].record_failure()

            # Exponential backoff before retry
            if attempt < self.max_retries - 1:
                backoff = self.backoff_base**attempt
                logger.info(f"⏳ Backing off for {backoff}s before retry...")
                await asyncio.sleep(backoff)

        # All attempts failed
        error_msg = (
            f"❌ All {self.max_retries} streaming attempts failed on all endpoints. "
            f"Last error: {last_exception}"
        )
        logger.error(error_msg)
        raise Exception(error_msg)

    async def _get_next_healthy_endpoint(self) -> Optional[EndpointConfig]:
        """Get next healthy endpoint using round-robin

        Returns:
            EndpointConfig if healthy endpoint found, None otherwise
        """
        current_time = time.time()

        # Check if health checks needed
        for ep in self.endpoints:
            time_since_check = current_time - self.health[ep.name].last_health_check
            if time_since_check > self.health_check_interval:
                await self._check_endpoint_health(ep)

        # Round-robin through healthy endpoints
        async with self._index_lock:
            for _ in range(len(self.endpoints)):
                ep = self.endpoints[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.endpoints)

                if self.health[ep.name].is_healthy:
                    logger.debug(f"🎯 Selected endpoint: {ep.name}")
                    return ep

        logger.warning("⚠️  No healthy endpoints available")
        return None

    async def _check_endpoint_health(self, endpoint: EndpointConfig):
        """Check if endpoint is healthy

        This is a simple health check. In production, you might want to
        call a specific /health endpoint if available.

        Args:
            endpoint: Endpoint to check
        """
        try:
            # Simple check: try to create a client and make a minimal request
            client = self.clients[endpoint.name]

            # Try a minimal completion request with very short timeout
            test_response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1,
                ),
                timeout=5.0,  # Short timeout for health check
            )

            self.health[endpoint.name].record_health_check(success=True)
            logger.debug(f"✅ Health check passed for {endpoint.name}")

        except Exception as e:
            self.health[endpoint.name].record_health_check(success=False)
            logger.debug(f"❌ Health check failed for {endpoint.name}: {e}")

    def get_health_stats(self) -> Dict[str, Any]:
        """Get health statistics for all endpoints

        Returns:
            Dictionary with health stats per endpoint
        """
        return {
            "endpoints": [health.get_stats() for health in self.health.values()],
            "total_endpoints": len(self.endpoints),
            "healthy_endpoints": sum(
                1 for health in self.health.values() if health.is_healthy
            ),
        }

    async def close(self):
        """Close all client connections"""
        for client in self.clients.values():
            await client.close()
        logger.info("🔌 All LLM client connections closed")


# Convenience function for creating client from config
def create_llm_client_from_config(config: Dict[str, Any]) -> DualEndpointLLMClient:
    """Create DualEndpointLLMClient from configuration dict

    Args:
        config: Configuration dictionary with 'llm' section

    Returns:
        Initialized DualEndpointLLMClient

    Example:
        >>> config = {
        ...     "llm": {
        ...         "model_name": "gpt-oss-120b",
        ...         "endpoints": [
        ...             {"url": "http://localhost:8001/v1", "name": "primary", "timeout": 120},
        ...             {"url": "http://localhost:8002/v1", "name": "secondary", "timeout": 120}
        ...         ],
        ...         "health_check": {"interval_seconds": 30},
        ...         "retry": {"max_attempts": 4, "backoff_base": 2}
        ...     }
        ... }
        >>> client = create_llm_client_from_config(config)
    """
    llm_config = config["llm"]

    # Parse endpoints
    endpoints = [
        EndpointConfig(
            url=ep["url"],
            name=ep["name"],
            timeout=ep.get("timeout", 120),
        )
        for ep in llm_config["endpoints"]
    ]

    # Create client
    return DualEndpointLLMClient(
        endpoints=endpoints,
        model_name=llm_config["model_name"],
        health_check_interval=llm_config["health_check"]["interval_seconds"],
        max_retries=llm_config["retry"]["max_attempts"],
        backoff_base=llm_config["retry"]["backoff_base"],
    )
