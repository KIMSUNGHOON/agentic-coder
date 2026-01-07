"""HTTP Client with Retry Logic for LLM Endpoints.

Provides robust HTTP client with exponential backoff retry for:
- httpx.ConnectError (connection failures)
- httpx.TimeoutException (request timeouts)
- HTTP 5xx errors (server errors)
"""

import logging
import time
import httpx
from typing import Dict, Any, Optional, Tuple
from functools import wraps

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_TIMEOUT = 120  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 2  # seconds


class LLMHttpClient:
    """HTTP client optimized for LLM endpoint calls with retry logic.

    Features:
    - Exponential backoff retry for connection and timeout errors
    - Configurable timeout and retry settings
    - Detailed logging for debugging
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: int = DEFAULT_BASE_DELAY
    ):
        """Initialize HTTP client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff (2^attempt * base_delay)
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay

    def post(
        self,
        url: str,
        json: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Make POST request with retry logic.

        Args:
            url: Target URL
            json: JSON payload
            headers: Optional headers

        Returns:
            Tuple of (response_json, error_message)
            - On success: (dict, None)
            - On failure: (None, error_string)
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(url, json=json, headers=headers)

                    if response.status_code == 200:
                        return response.json(), None

                    # Handle server errors (5xx) with retry
                    if 500 <= response.status_code < 600:
                        error_msg = f"Server error {response.status_code}: {response.text[:200]}"
                        logger.warning(f"[HTTP] {error_msg} (attempt {attempt + 1}/{self.max_retries})")
                        last_error = error_msg

                        if attempt < self.max_retries - 1:
                            self._wait_with_backoff(attempt)
                            continue

                    # Non-retryable client errors (4xx)
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"[HTTP] Non-retryable error: {error_msg}")
                    return None, error_msg

            except httpx.ConnectError as e:
                last_error = f"Connection error: {str(e)}"
                logger.warning(
                    f"[HTTP] ConnectError (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

                if attempt < self.max_retries - 1:
                    self._wait_with_backoff(attempt)
                else:
                    logger.error(f"[HTTP] Connection failed after {self.max_retries} attempts")

            except httpx.TimeoutException as e:
                last_error = f"Timeout error: {str(e)}"
                logger.warning(
                    f"[HTTP] TimeoutException (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

                if attempt < self.max_retries - 1:
                    self._wait_with_backoff(attempt)
                else:
                    logger.error(f"[HTTP] Timeout after {self.max_retries} attempts")

            except httpx.HTTPStatusError as e:
                last_error = f"HTTP status error: {str(e)}"
                logger.error(f"[HTTP] HTTPStatusError: {e}")
                return None, last_error

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(f"[HTTP] Unexpected error: {e}", exc_info=True)
                return None, last_error

        return None, last_error

    def _wait_with_backoff(self, attempt: int) -> None:
        """Wait with exponential backoff.

        Args:
            attempt: Current attempt number (0-indexed)
        """
        wait_time = self.base_delay * (2 ** attempt)
        logger.info(f"[HTTP] Retrying in {wait_time}s...")
        time.sleep(wait_time)


class AsyncLLMHttpClient:
    """Async HTTP client optimized for LLM endpoint calls with retry logic.

    Features:
    - Exponential backoff retry for connection and timeout errors
    - Async/await support
    - Configurable timeout and retry settings
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        base_delay: int = DEFAULT_BASE_DELAY
    ):
        """Initialize async HTTP client.

        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def post(
        self,
        url: str,
        json: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Make async POST request with retry logic.

        Args:
            url: Target URL
            json: JSON payload
            headers: Optional headers

        Returns:
            Tuple of (response_json, error_message)
        """
        import asyncio
        last_error = None

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=json, headers=headers)

                    if response.status_code == 200:
                        return response.json(), None

                    # Handle server errors (5xx) with retry
                    if 500 <= response.status_code < 600:
                        error_msg = f"Server error {response.status_code}"
                        logger.warning(f"[HTTP] {error_msg} (attempt {attempt + 1}/{self.max_retries})")
                        last_error = error_msg

                        if attempt < self.max_retries - 1:
                            await self._async_wait_with_backoff(attempt)
                            continue

                    # Non-retryable client errors (4xx)
                    error_msg = f"HTTP {response.status_code}"
                    logger.error(f"[HTTP] Non-retryable error: {error_msg}")
                    return None, error_msg

            except httpx.ConnectError as e:
                last_error = f"Connection error: {str(e)}"
                logger.warning(
                    f"[HTTP] ConnectError (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

                if attempt < self.max_retries - 1:
                    await self._async_wait_with_backoff(attempt)
                else:
                    logger.error(f"[HTTP] Connection failed after {self.max_retries} attempts")

            except httpx.TimeoutException as e:
                last_error = f"Timeout error: {str(e)}"
                logger.warning(
                    f"[HTTP] TimeoutException (attempt {attempt + 1}/{self.max_retries}): {e}"
                )

                if attempt < self.max_retries - 1:
                    await self._async_wait_with_backoff(attempt)
                else:
                    logger.error(f"[HTTP] Timeout after {self.max_retries} attempts")

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                logger.error(f"[HTTP] Unexpected error: {e}", exc_info=True)
                return None, last_error

        return None, last_error

    async def _async_wait_with_backoff(self, attempt: int) -> None:
        """Wait with exponential backoff (async).

        Args:
            attempt: Current attempt number (0-indexed)
        """
        import asyncio
        wait_time = self.base_delay * (2 ** attempt)
        logger.info(f"[HTTP] Retrying in {wait_time}s...")
        await asyncio.sleep(wait_time)


# Helper function for simple LLM calls
def llm_post_with_retry(
    endpoint: str,
    model: str,
    messages: list,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    stop: Optional[list] = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Make LLM API call with retry logic.

    Convenience function for making chat/completions calls.

    Args:
        endpoint: LLM endpoint base URL (e.g., http://localhost:8001/v1)
        model: Model name
        messages: Chat messages
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        stop: Stop sequences
        timeout: Request timeout
        max_retries: Maximum retry attempts

    Returns:
        Tuple of (response_json, error_message)

    Example:
        response, error = llm_post_with_retry(
            endpoint="http://localhost:8001/v1",
            model="deepseek-ai/DeepSeek-R1",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"}
            ]
        )
        if error:
            print(f"Error: {error}")
        else:
            content = response["choices"][0]["message"]["content"]
    """
    client = LLMHttpClient(timeout=timeout, max_retries=max_retries)

    url = f"{endpoint}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    if stop:
        payload["stop"] = stop

    return client.post(url, json=payload)


# Global client instances for convenience
_sync_client: Optional[LLMHttpClient] = None
_async_client: Optional[AsyncLLMHttpClient] = None


def get_http_client() -> LLMHttpClient:
    """Get or create singleton sync HTTP client."""
    global _sync_client
    if _sync_client is None:
        _sync_client = LLMHttpClient()
    return _sync_client


def get_async_http_client() -> AsyncLLMHttpClient:
    """Get or create singleton async HTTP client."""
    global _async_client
    if _async_client is None:
        _async_client = AsyncLLMHttpClient()
    return _async_client
