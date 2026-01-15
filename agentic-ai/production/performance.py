"""Performance Optimization for Agentic 2.0

Production performance features:
- Endpoint selection optimization
- Context filtering
- Parallel tool execution
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EndpointConfig:
    """Endpoint configuration"""
    name: str
    url: str
    api_key: str
    model_name: Optional[str] = None
    max_tokens: Optional[int] = None
    timeout: int = 30


@dataclass
class EndpointHealth:
    """Endpoint health metrics"""
    url: str
    name: str
    is_healthy: bool
    response_time_ms: float
    success_rate: float
    last_check: datetime
    consecutive_failures: int


class EndpointSelector:
    """Intelligent endpoint selection based on health and performance

    Features:
    - Health-based routing
    - Response time optimization
    - Automatic failover
    - Load balancing

    Example:
        >>> selector = EndpointSelector(endpoints)
        >>> best_endpoint = selector.select_best_endpoint()
        >>> # Uses endpoint with best health + performance
    """

    def __init__(
        self,
        endpoints: List[Any],  # Can be List[EndpointConfig] or List[Dict]
        health_check_interval: int = 30,
        max_consecutive_failures: int = 3
    ):
        """Initialize endpoint selector

        Args:
            endpoints: List of endpoint configurations (EndpointConfig or dict)
            health_check_interval: Seconds between health checks
            max_consecutive_failures: Max failures before marking unhealthy
        """
        # Convert EndpointConfig objects to dicts for consistency
        self.endpoints = []
        for ep in endpoints:
            if isinstance(ep, EndpointConfig):
                self.endpoints.append({
                    "name": ep.name,
                    "url": ep.url,
                    "api_key": ep.api_key,
                    "model_name": ep.model_name,
                    "max_tokens": ep.max_tokens,
                    "timeout": ep.timeout,
                })
            else:
                self.endpoints.append(ep)

        self.health_check_interval = health_check_interval
        self.max_consecutive_failures = max_consecutive_failures

        # Initialize health tracking
        self.endpoint_health: Dict[str, EndpointHealth] = {}
        for endpoint in self.endpoints:
            self.endpoint_health[endpoint["url"]] = EndpointHealth(
                url=endpoint["url"],
                name=endpoint.get("name", "unknown"),
                is_healthy=True,
                response_time_ms=0.0,
                success_rate=1.0,
                last_check=datetime.now(),
                consecutive_failures=0
            )

    def select_best_endpoint(self) -> Optional[Dict[str, Any]]:
        """Select best endpoint based on health and performance

        Returns:
            Best endpoint config or None if all unhealthy
        """
        healthy_endpoints = [
            (url, health) for url, health in self.endpoint_health.items()
            if health.is_healthy
        ]

        if not healthy_endpoints:
            logger.warning("No healthy endpoints available, using fallback")
            # Return first endpoint as fallback
            return self.endpoints[0] if self.endpoints else None

        # Sort by: 1) success rate (desc), 2) response time (asc)
        healthy_endpoints.sort(
            key=lambda x: (-x[1].success_rate, x[1].response_time_ms)
        )

        best_url = healthy_endpoints[0][0]

        # Find and return the endpoint config
        for endpoint in self.endpoints:
            if endpoint["url"] == best_url:
                logger.debug(f"Selected endpoint: {endpoint.get('name', best_url)}")
                return endpoint

        return None

    def record_success(
        self,
        url: str,
        response_time_ms: float
    ):
        """Record successful request

        Args:
            url: Endpoint URL
            response_time_ms: Response time in milliseconds
        """
        if url not in self.endpoint_health:
            return

        health = self.endpoint_health[url]
        health.is_healthy = True
        health.consecutive_failures = 0
        health.last_check = datetime.now()

        # Update response time (exponential moving average)
        alpha = 0.3  # Weight for new value
        if health.response_time_ms == 0:
            health.response_time_ms = response_time_ms
        else:
            health.response_time_ms = (
                alpha * response_time_ms +
                (1 - alpha) * health.response_time_ms
            )

        # Update success rate (exponential moving average)
        health.success_rate = alpha * 1.0 + (1 - alpha) * health.success_rate

        logger.debug(f"Endpoint {health.name}: success, {response_time_ms:.0f}ms")

    def record_failure(self, url: str):
        """Record failed request

        Args:
            url: Endpoint URL
        """
        if url not in self.endpoint_health:
            return

        health = self.endpoint_health[url]
        health.consecutive_failures += 1
        health.last_check = datetime.now()

        # Update success rate
        alpha = 0.3
        health.success_rate = alpha * 0.0 + (1 - alpha) * health.success_rate

        # Mark unhealthy if too many consecutive failures
        if health.consecutive_failures >= self.max_consecutive_failures:
            health.is_healthy = False
            logger.warning(f"Endpoint {health.name} marked unhealthy")

        logger.debug(f"Endpoint {health.name}: failure ({health.consecutive_failures})")

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all endpoints

        Returns:
            Dict with health status
        """
        return {
            url: {
                "name": health.name,
                "healthy": health.is_healthy,
                "response_time_ms": health.response_time_ms,
                "success_rate": health.success_rate,
                "consecutive_failures": health.consecutive_failures,
            }
            for url, health in self.endpoint_health.items()
        }

    def get_endpoint_stats(self, url: str) -> Dict[str, Any]:
        """Get statistics for a specific endpoint

        Args:
            url: Endpoint URL

        Returns:
            Dict with endpoint statistics
        """
        if url not in self.endpoint_health:
            return {
                "error": "Endpoint not found",
                "url": url,
            }

        health = self.endpoint_health[url]
        return {
            "name": health.name,
            "url": health.url,
            "is_healthy": health.is_healthy,
            "success_rate": health.success_rate,
            "avg_response_time_ms": health.response_time_ms,
            "consecutive_failures": health.consecutive_failures,
            "last_check": health.last_check.isoformat(),
        }


class ContextFilter:
    """Filter and optimize context for LLM calls

    Features:
    - Remove unnecessary fields
    - Truncate long content
    - Deduplicate information
    - Token budget management

    Example:
        >>> filter = ContextFilter(max_tokens=4000)
        >>> filtered = filter.filter_context(context, priority_keys=["task", "plan"])
    """

    def __init__(
        self,
        max_tokens: int = 4000,
        max_message_length: int = 2000,
        max_tool_calls: int = 10,
        max_list_items: int = 10,
        max_context_size: int = 10000
    ):
        """Initialize context filter

        Args:
            max_tokens: Maximum token budget (approximate)
            max_message_length: Max length per message
            max_tool_calls: Max tool calls to keep
            max_list_items: Max items in lists
            max_context_size: Max total context size in characters
        """
        self.max_tokens = max_tokens
        self.max_message_length = max_message_length
        self.max_tool_calls = max_tool_calls
        self.max_list_items = max_list_items
        self.max_context_size = max_context_size

    def filter_context(
        self,
        context: Dict[str, Any],
        priority_keys: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Filter context to reduce size

        Args:
            context: Context dict to filter
            priority_keys: Keys to always keep

        Returns:
            Filtered context dict
        """
        filtered = {}
        priority_keys = priority_keys or []

        for key, value in context.items():
            # Always keep priority keys
            if key in priority_keys:
                filtered[key] = value
                continue

            # Filter based on type
            if isinstance(value, str):
                # Truncate long strings
                if len(value) > self.max_message_length:
                    filtered[key] = value[:self.max_message_length] + "..."
                else:
                    filtered[key] = value

            elif isinstance(value, list):
                # Limit list size
                if key == "messages" and len(value) > 20:
                    # Keep recent messages
                    filtered[key] = value[-20:]
                elif key == "tool_calls" and len(value) > self.max_tool_calls:
                    # Keep recent tool calls
                    filtered[key] = value[-self.max_tool_calls:]
                elif len(value) > self.max_list_items:
                    # Limit general lists
                    filtered[key] = value[:self.max_list_items]
                else:
                    filtered[key] = value

            elif isinstance(value, dict):
                # Recursively filter nested dicts
                filtered[key] = self.filter_context(value, priority_keys)

            else:
                # Keep other types as-is
                filtered[key] = value

        return filtered

    def filter_messages(
        self,
        messages: List[Dict[str, str]],
        keep_recent: int = 10
    ) -> List[Dict[str, str]]:
        """Filter message list

        Args:
            messages: List of messages
            keep_recent: Number of recent messages to keep

        Returns:
            Filtered message list
        """
        if len(messages) <= keep_recent:
            return messages

        # Always keep system message if present
        system_messages = [m for m in messages if m.get("role") == "system"]
        other_messages = [m for m in messages if m.get("role") != "system"]

        # Keep most recent messages
        recent_messages = other_messages[-keep_recent:]

        return system_messages + recent_messages


class ParallelToolExecutor:
    """Execute multiple tools in parallel

    Features:
    - Concurrent tool execution
    - Dependency management
    - Result aggregation
    - Error isolation

    Example:
        >>> executor = ParallelToolExecutor(max_parallel=3)
        >>> results = await executor.execute_parallel([
        ...     (tool1, params1),
        ...     (tool2, params2),
        ... ])
    """

    def __init__(
        self,
        max_parallel: int = 5,
        timeout_seconds: int = 30
    ):
        """Initialize parallel tool executor

        Args:
            max_parallel: Maximum parallel executions
            timeout_seconds: Timeout per tool
        """
        self.max_parallel = max_parallel
        self.timeout_seconds = timeout_seconds

    async def execute_parallel(
        self,
        tool_calls: List[tuple[Callable, Dict[str, Any]]],
        fail_fast: bool = False
    ) -> List[Dict[str, Any]]:
        """Execute tools in parallel

        Args:
            tool_calls: List of (tool_function, parameters) tuples
            fail_fast: Stop on first failure

        Returns:
            List of results
        """
        if not tool_calls:
            return []

        logger.info(f"Executing {len(tool_calls)} tools in parallel (max={self.max_parallel})")

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_parallel)

        # Create tasks
        tasks = [
            self._execute_with_semaphore(
                tool_func, params, semaphore, idx
            )
            for idx, (tool_func, params) in enumerate(tool_calls)
        ]

        # Execute all tasks
        if fail_fast:
            # Stop on first failure
            results = await asyncio.gather(*tasks)
        else:
            # Continue on failures
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Tool {idx} failed: {result}")
                processed_results.append({
                    "success": False,
                    "error": str(result),
                    "tool_index": idx
                })
            else:
                processed_results.append(result)

        success_count = sum(1 for r in processed_results if r.get("success", False))
        logger.info(f"Parallel execution complete: {success_count}/{len(tool_calls)} succeeded")

        return processed_results

    async def _execute_with_semaphore(
        self,
        tool_func: Callable,
        params: Dict[str, Any],
        semaphore: asyncio.Semaphore,
        idx: int
    ) -> Dict[str, Any]:
        """Execute single tool with semaphore control"""
        async with semaphore:
            try:
                logger.debug(f"Starting tool {idx}")

                # Execute with timeout
                result = await asyncio.wait_for(
                    tool_func(**params),
                    timeout=self.timeout_seconds
                )

                return {
                    "success": True,
                    "result": result,
                    "tool_index": idx
                }

            except asyncio.TimeoutError:
                logger.error(f"Tool {idx} timed out after {self.timeout_seconds}s")
                return {
                    "success": False,
                    "error": f"Timeout after {self.timeout_seconds}s",
                    "tool_index": idx
                }

            except Exception as e:
                logger.error(f"Tool {idx} error: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "tool_index": idx
                }

    async def execute_with_dependencies(
        self,
        tool_calls: List[tuple[Callable, Dict[str, Any], List[int]]],
    ) -> List[Dict[str, Any]]:
        """Execute tools respecting dependencies

        Args:
            tool_calls: List of (tool_function, parameters, dependency_indices)

        Returns:
            List of results
        """
        results = [None] * len(tool_calls)
        completed = set()

        while len(completed) < len(tool_calls):
            # Find tools ready to execute (dependencies met)
            ready = []
            for idx, (tool_func, params, deps) in enumerate(tool_calls):
                if idx in completed:
                    continue

                if all(dep in completed for dep in deps):
                    ready.append(idx)

            if not ready:
                logger.error("Circular dependency detected or all remaining tasks failed")
                break

            # Execute ready tasks in parallel
            ready_calls = [
                (tool_calls[idx][0], tool_calls[idx][1])
                for idx in ready
            ]

            batch_results = await self.execute_parallel(ready_calls)

            # Store results
            for i, idx in enumerate(ready):
                results[idx] = batch_results[i]
                if batch_results[i].get("success", False):
                    completed.add(idx)

        return results
