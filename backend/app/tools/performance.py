"""
Performance Optimization Module for Agent Tools

Features:
1. ConnectionPool - Shared aiohttp ClientSession with connection pooling
2. ProgressTracker - Download progress tracking with callbacks
3. ResultCache - LRU cache for tool results

Phase 3: Performance Optimization
"""

import asyncio
import hashlib
import json
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


# =============================================================================
# Connection Pool
# =============================================================================

class ConnectionPool:
    """
    Shared HTTP connection pool using aiohttp.

    Benefits:
    - Reuse TCP connections (avoid handshake overhead)
    - DNS caching
    - Keep-alive connections
    - Configurable limits

    Usage:
        pool = ConnectionPool.get_instance()
        async with pool.get_session() as session:
            async with session.get(url) as response:
                ...
    """

    _instance: Optional["ConnectionPool"] = None
    _lock = asyncio.Lock()

    def __init__(
        self,
        max_connections: int = 100,
        max_connections_per_host: int = 10,
        keepalive_timeout: int = 30,
        dns_cache_ttl: int = 300
    ):
        self._max_connections = max_connections
        self._max_per_host = max_connections_per_host
        self._keepalive_timeout = keepalive_timeout
        self._dns_cache_ttl = dns_cache_ttl

        self._session: Optional[Any] = None
        self._connector: Optional[Any] = None
        self._request_count = 0
        self._created_at: Optional[float] = None

    @classmethod
    async def get_instance(cls) -> "ConnectionPool":
        """Get singleton instance (thread-safe)"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance._initialize()
        return cls._instance

    async def _initialize(self):
        """Initialize aiohttp session with connection pooling"""
        try:
            import aiohttp

            # Create connector with connection pooling
            self._connector = aiohttp.TCPConnector(
                limit=self._max_connections,
                limit_per_host=self._max_per_host,
                keepalive_timeout=self._keepalive_timeout,
                ttl_dns_cache=self._dns_cache_ttl,
                enable_cleanup_closed=True
            )

            # Create session with default timeout
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout
            )

            self._created_at = time.time()
            logger.info(
                f"ConnectionPool initialized: max={self._max_connections}, "
                f"per_host={self._max_per_host}"
            )

        except ImportError:
            logger.warning("aiohttp not installed - connection pooling disabled")
            self._session = None

    @asynccontextmanager
    async def get_session(self, timeout: Optional[int] = None):
        """
        Get the shared session with optional custom timeout.

        Args:
            timeout: Optional timeout override in seconds

        Yields:
            aiohttp.ClientSession
        """
        if self._session is None:
            await self._initialize()

        if self._session is None:
            raise RuntimeError("Failed to initialize HTTP session")

        self._request_count += 1

        if timeout:
            import aiohttp
            custom_timeout = aiohttp.ClientTimeout(total=timeout)
            # Create a new session with custom timeout but shared connector
            async with aiohttp.ClientSession(
                connector=self._connector,
                connector_owner=False,  # Don't close shared connector
                timeout=custom_timeout
            ) as custom_session:
                yield custom_session
        else:
            yield self._session

    async def close(self):
        """Close the connection pool"""
        if self._session:
            await self._session.close()
            self._session = None
        if self._connector:
            await self._connector.close()
            self._connector = None
        logger.info(f"ConnectionPool closed after {self._request_count} requests")

    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        stats = {
            "request_count": self._request_count,
            "max_connections": self._max_connections,
            "max_per_host": self._max_per_host,
            "initialized": self._session is not None
        }

        if self._created_at:
            stats["uptime_seconds"] = int(time.time() - self._created_at)

        if self._connector:
            stats["active_connections"] = len(self._connector._acquired)

        return stats

    @classmethod
    async def reset_instance(cls):
        """Reset singleton instance (for testing)"""
        if cls._instance:
            await cls._instance.close()
            cls._instance = None


# =============================================================================
# Progress Tracker
# =============================================================================

@dataclass
class DownloadProgress:
    """Download progress information"""
    url: str
    output_path: str
    total_bytes: int = 0
    downloaded_bytes: int = 0
    speed_bps: float = 0.0  # bytes per second
    eta_seconds: float = 0.0
    started_at: float = field(default_factory=time.time)
    status: str = "starting"  # starting, downloading, completed, failed

    @property
    def percent(self) -> float:
        if self.total_bytes == 0:
            return 0.0
        return min(100.0, (self.downloaded_bytes / self.total_bytes) * 100)

    @property
    def speed_mbps(self) -> float:
        return self.speed_bps / (1024 * 1024)

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "output_path": self.output_path,
            "total_bytes": self.total_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "percent": round(self.percent, 1),
            "speed_mbps": round(self.speed_mbps, 2),
            "eta_seconds": round(self.eta_seconds, 1),
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "status": self.status
        }


class ProgressTracker:
    """
    Track download progress with callbacks.

    Usage:
        tracker = ProgressTracker(
            url="https://example.com/file.zip",
            output_path="/tmp/file.zip",
            total_bytes=1000000,
            callback=my_progress_callback
        )

        async for chunk in response.content.iter_chunked(8192):
            await tracker.update(len(chunk))

        tracker.complete()
    """

    def __init__(
        self,
        url: str,
        output_path: str,
        total_bytes: int = 0,
        callback: Optional[Callable[[DownloadProgress], None]] = None,
        update_interval: float = 0.5  # seconds
    ):
        self.progress = DownloadProgress(
            url=url,
            output_path=output_path,
            total_bytes=total_bytes
        )
        self._callback = callback
        self._update_interval = update_interval
        self._last_update = 0.0
        self._last_bytes = 0
        self._last_time = time.time()

    async def update(self, bytes_received: int):
        """Update progress with received bytes"""
        self.progress.downloaded_bytes += bytes_received
        self.progress.status = "downloading"

        current_time = time.time()

        # Throttle updates
        if current_time - self._last_update < self._update_interval:
            return

        # Calculate speed
        time_delta = current_time - self._last_time
        if time_delta > 0:
            bytes_delta = self.progress.downloaded_bytes - self._last_bytes
            self.progress.speed_bps = bytes_delta / time_delta

            # Calculate ETA
            if self.progress.speed_bps > 0 and self.progress.total_bytes > 0:
                remaining = self.progress.total_bytes - self.progress.downloaded_bytes
                self.progress.eta_seconds = remaining / self.progress.speed_bps
            else:
                self.progress.eta_seconds = 0

        self._last_bytes = self.progress.downloaded_bytes
        self._last_time = current_time
        self._last_update = current_time

        # Call callback
        if self._callback:
            try:
                self._callback(self.progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")

    def complete(self, success: bool = True):
        """Mark download as complete"""
        self.progress.status = "completed" if success else "failed"
        self.progress.downloaded_bytes = self.progress.total_bytes

        if self._callback:
            try:
                self._callback(self.progress)
            except Exception:
                pass

    def get_progress(self) -> DownloadProgress:
        """Get current progress"""
        return self.progress


# =============================================================================
# Result Cache
# =============================================================================

class ResultCache:
    """
    LRU cache for tool execution results.

    Features:
    - LRU eviction policy
    - TTL (time-to-live) support
    - Configurable max size
    - Cache key generation from params

    Usage:
        cache = ResultCache(max_size=100, ttl_seconds=300)

        # Try cache first
        result = cache.get("tool_name", {"param": "value"})
        if result:
            return result

        # Execute tool
        result = await tool.execute(...)

        # Cache result
        cache.set("tool_name", {"param": "value"}, result)
    """

    def __init__(
        self,
        max_size: int = 100,
        ttl_seconds: int = 300,
        enabled: bool = True
    ):
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._enabled = enabled
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def _make_key(self, tool_name: str, params: Dict[str, Any]) -> str:
        """Generate cache key from tool name and parameters"""
        # Sort params for consistent key generation
        sorted_params = json.dumps(params, sort_keys=True, default=str)
        key_string = f"{tool_name}:{sorted_params}"
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def _is_expired(self, timestamp: float) -> bool:
        """Check if cache entry is expired"""
        return time.time() - timestamp > self._ttl_seconds

    def get(self, tool_name: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        Get cached result.

        Args:
            tool_name: Name of the tool
            params: Tool execution parameters

        Returns:
            Cached result or None if not found/expired
        """
        if not self._enabled:
            return None

        key = self._make_key(tool_name, params)

        if key not in self._cache:
            self._misses += 1
            return None

        result, timestamp = self._cache[key]

        # Check expiration
        if self._is_expired(timestamp):
            del self._cache[key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1

        logger.debug(f"Cache hit for {tool_name}")
        return result

    def set(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: Any,
        ttl_override: Optional[int] = None
    ):
        """
        Cache a result.

        Args:
            tool_name: Name of the tool
            params: Tool execution parameters
            result: Result to cache
            ttl_override: Optional TTL override for this entry
        """
        if not self._enabled:
            return

        key = self._make_key(tool_name, params)

        # Remove if exists (to update position)
        if key in self._cache:
            del self._cache[key]

        # Evict oldest if at capacity
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        # Store with timestamp
        timestamp = time.time()
        if ttl_override:
            # Adjust timestamp for custom TTL
            timestamp = time.time() - (self._ttl_seconds - ttl_override)

        self._cache[key] = (result, timestamp)
        logger.debug(f"Cached result for {tool_name}")

    def invalidate(self, tool_name: str, params: Optional[Dict[str, Any]] = None):
        """
        Invalidate cache entries.

        Args:
            tool_name: Name of the tool
            params: If provided, invalidate specific entry; otherwise invalidate all for tool
        """
        if params:
            key = self._make_key(tool_name, params)
            if key in self._cache:
                del self._cache[key]
        else:
            # Remove all entries for this tool
            prefix = hashlib.sha256(f"{tool_name}:".encode()).hexdigest()[:8]
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]

    def clear(self):
        """Clear all cached entries"""
        self._cache.clear()
        logger.info("Cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "enabled": self._enabled,
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl_seconds": self._ttl_seconds,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": round(hit_rate, 1)
        }


# =============================================================================
# Global Instances
# =============================================================================

# Lazy-initialized global cache
_global_cache: Optional[ResultCache] = None


def get_cache() -> ResultCache:
    """Get global result cache instance"""
    global _global_cache
    if _global_cache is None:
        _global_cache = ResultCache(
            max_size=100,
            ttl_seconds=300,
            enabled=True
        )
    return _global_cache


def reset_cache():
    """Reset global cache (for testing)"""
    global _global_cache
    if _global_cache:
        _global_cache.clear()
    _global_cache = None
