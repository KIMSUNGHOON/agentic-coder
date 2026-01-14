"""Performance Optimization Module for Agentic 2.0

Provides caching and optimization utilities:
- LLM response caching
- State size management
- Resource pooling
- Performance monitoring
"""

import logging
import hashlib
import json
import time
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with TTL"""
    value: Any
    created_at: float
    hits: int = 0
    ttl: float = 300.0  # 5 minutes default

    def is_expired(self) -> bool:
        """Check if cache entry is expired"""
        return time.time() - self.created_at > self.ttl


class LRUCache:
    """LRU Cache with TTL support

    Features:
    - Least Recently Used eviction
    - Time-to-live (TTL) expiration
    - Hit/miss tracking
    - Size limits

    Example:
        >>> cache = LRUCache(max_size=100, default_ttl=300)
        >>> cache.set("key", "value")
        >>> value = cache.get("key")
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        """Initialize LRU Cache

        Args:
            max_size: Maximum number of entries (default: 1000)
            default_ttl: Default TTL in seconds (default: 300)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]

        # Check expiration
        if entry.is_expired():
            del self._cache[key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        entry.hits += 1
        self._hits += 1

        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Optional TTL override
        """
        # Remove expired entries if cache is full
        if len(self._cache) >= self.max_size:
            self._evict_expired()

        # Evict LRU if still full
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)  # Remove oldest

        # Add entry
        entry = CacheEntry(
            value=value,
            created_at=time.time(),
            ttl=ttl or self.default_ttl
        )

        self._cache[key] = entry
        self._cache.move_to_end(key)

    def _evict_expired(self):
        """Remove expired entries"""
        keys_to_delete = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]

        for key in keys_to_delete:
            del self._cache[key]

    def clear(self):
        """Clear all cache entries"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics

        Returns:
            Dictionary with cache stats
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }


class LLMResponseCache:
    """Cache for LLM responses

    Caches LLM responses to avoid duplicate API calls.
    Uses message content + parameters as cache key.

    Example:
        >>> cache = LLMResponseCache()
        >>> response = await cache.get_or_call(messages, llm_func, temperature=0.7)
    """

    def __init__(self, max_size: int = 500, ttl: float = 3600.0):
        """Initialize LLM response cache

        Args:
            max_size: Maximum cached responses (default: 500)
            ttl: TTL in seconds (default: 3600 = 1 hour)
        """
        self.cache = LRUCache(max_size=max_size, default_ttl=ttl)
        self.enabled = True

        logger.info(f"💾 LLM Response Cache initialized (size: {max_size}, TTL: {ttl}s)")

    def _generate_key(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> str:
        """Generate cache key from messages and parameters

        Args:
            messages: List of messages
            **kwargs: Additional parameters

        Returns:
            Cache key (hash)
        """
        # Create deterministic representation
        cache_data = {
            "messages": messages,
            "params": {
                k: v for k, v in sorted(kwargs.items())
                if k in ["temperature", "max_tokens", "model"]
            }
        }

        # Generate hash
        json_str = json.dumps(cache_data, sort_keys=True)
        key = hashlib.sha256(json_str.encode()).hexdigest()

        return key

    async def get_or_call(
        self,
        messages: List[Dict[str, str]],
        llm_func,
        **kwargs
    ) -> str:
        """Get cached response or call LLM

        Args:
            messages: List of messages
            llm_func: Async LLM function to call
            **kwargs: Additional parameters

        Returns:
            LLM response content
        """
        if not self.enabled:
            return await llm_func(messages, **kwargs)

        # Generate cache key
        key = self._generate_key(messages, **kwargs)

        # Check cache
        cached = self.cache.get(key)
        if cached is not None:
            logger.debug(f"💾 Cache HIT: {key[:16]}...")
            return cached

        # Cache miss - call LLM
        logger.debug(f"💾 Cache MISS: {key[:16]}...")
        response = await llm_func(messages, **kwargs)

        # Cache response
        self.cache.set(key, response)

        return response

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()

    def clear(self):
        """Clear cache"""
        self.cache.clear()
        logger.info("💾 LLM cache cleared")


class StateOptimizer:
    """Optimizer for AgenticState

    Prevents state from growing too large by:
    - Truncating old messages
    - Limiting tool call history
    - Compressing context

    Example:
        >>> optimizer = StateOptimizer()
        >>> state = optimizer.optimize(state)
    """

    def __init__(
        self,
        max_messages: int = 20,
        max_tool_calls: int = 50,
        max_context_size_kb: int = 100,
    ):
        """Initialize State Optimizer

        Args:
            max_messages: Max messages to keep (default: 20)
            max_tool_calls: Max tool calls to keep (default: 50)
            max_context_size_kb: Max context size in KB (default: 100)
        """
        self.max_messages = max_messages
        self.max_tool_calls = max_tool_calls
        self.max_context_size_kb = max_context_size_kb

    def optimize(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize state size

        Args:
            state: State to optimize

        Returns:
            Optimized state
        """
        # Truncate messages (keep most recent)
        if "messages" in state and len(state["messages"]) > self.max_messages:
            state["messages"] = state["messages"][-self.max_messages:]
            logger.debug(f"📦 Truncated messages to {self.max_messages}")

        # Truncate tool calls (keep most recent)
        if "tool_calls" in state and len(state["tool_calls"]) > self.max_tool_calls:
            state["tool_calls"] = state["tool_calls"][-self.max_tool_calls:]
            logger.debug(f"📦 Truncated tool calls to {self.max_tool_calls}")

        # Check context size
        if "context" in state:
            context_str = json.dumps(state["context"])
            size_kb = len(context_str) / 1024

            if size_kb > self.max_context_size_kb:
                logger.warning(f"📦 Context size large: {size_kb:.1f}KB")
                # Could implement compression here

        return state


class PerformanceMonitor:
    """Monitor performance metrics

    Tracks:
    - Execution times
    - LLM call counts
    - Memory usage
    - Cache hit rates

    Example:
        >>> monitor = PerformanceMonitor()
        >>> with monitor.measure("task_execution"):
        ...     await execute_task()
        >>> stats = monitor.get_stats()
    """

    def __init__(self):
        """Initialize Performance Monitor"""
        self.metrics: Dict[str, List[float]] = {}
        self.counts: Dict[str, int] = {}

    def record(self, metric: str, value: float):
        """Record a metric value

        Args:
            metric: Metric name
            value: Metric value
        """
        if metric not in self.metrics:
            self.metrics[metric] = []

        self.metrics[metric].append(value)

    def increment(self, counter: str):
        """Increment a counter

        Args:
            counter: Counter name
        """
        self.counts[counter] = self.counts.get(counter, 0) + 1

    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics

        Returns:
            Dictionary with stats
        """
        stats = {"metrics": {}, "counts": self.counts}

        for metric, values in self.metrics.items():
            if values:
                stats["metrics"][metric] = {
                    "count": len(values),
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "total": sum(values),
                }

        return stats

    def measure(self, name: str):
        """Context manager for measuring execution time

        Args:
            name: Measurement name

        Example:
            >>> with monitor.measure("operation"):
            ...     do_operation()
        """
        return _MeasureContext(self, name)


class _MeasureContext:
    """Context manager for performance measurement"""

    def __init__(self, monitor: PerformanceMonitor, name: str):
        self.monitor = monitor
        self.name = name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.monitor.record(self.name, duration)
        return False


# Global instances
_llm_cache = None
_state_optimizer = None
_performance_monitor = None


def get_llm_cache() -> LLMResponseCache:
    """Get global LLM response cache"""
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = LLMResponseCache()
    return _llm_cache


def get_state_optimizer() -> StateOptimizer:
    """Get global state optimizer"""
    global _state_optimizer
    if _state_optimizer is None:
        _state_optimizer = StateOptimizer()
    return _state_optimizer


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor
