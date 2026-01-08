"""
Tests for Phase 3 Performance Module

Tests:
- ConnectionPool: Connection pooling and reuse
- ProgressTracker: Download progress tracking
- ResultCache: LRU caching with TTL
"""

import os
import sys
import asyncio
import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from app.tools.performance import (
    ConnectionPool,
    ProgressTracker,
    DownloadProgress,
    ResultCache,
    get_cache,
    reset_cache
)


# =============================================================================
# ConnectionPool Tests
# =============================================================================

class TestConnectionPool:
    """Test ConnectionPool singleton and configuration"""

    @pytest.mark.asyncio
    async def test_singleton_pattern(self):
        """Test that get_instance returns same instance"""
        await ConnectionPool.reset_instance()

        pool1 = await ConnectionPool.get_instance()
        pool2 = await ConnectionPool.get_instance()

        assert pool1 is pool2

        await ConnectionPool.reset_instance()

    @pytest.mark.asyncio
    async def test_default_configuration(self):
        """Test default pool configuration"""
        await ConnectionPool.reset_instance()

        pool = await ConnectionPool.get_instance()

        assert pool._max_connections == 100
        assert pool._max_per_host == 10
        assert pool._keepalive_timeout == 30
        assert pool._dns_cache_ttl == 300

        await ConnectionPool.reset_instance()

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test statistics retrieval"""
        await ConnectionPool.reset_instance()

        pool = await ConnectionPool.get_instance()
        stats = pool.get_stats()

        assert "request_count" in stats
        assert "max_connections" in stats
        assert "initialized" in stats
        assert stats["max_connections"] == 100

        await ConnectionPool.reset_instance()

    @pytest.mark.asyncio
    async def test_request_count_increment(self):
        """Test that request count increments on session access"""
        await ConnectionPool.reset_instance()

        pool = await ConnectionPool.get_instance()

        initial_count = pool._request_count

        async with pool.get_session() as session:
            pass

        assert pool._request_count == initial_count + 1

        await ConnectionPool.reset_instance()


# =============================================================================
# ProgressTracker Tests
# =============================================================================

class TestDownloadProgress:
    """Test DownloadProgress dataclass"""

    def test_percent_calculation(self):
        """Test percent calculation"""
        progress = DownloadProgress(
            url="http://example.com/file",
            output_path="/tmp/file",
            total_bytes=1000,
            downloaded_bytes=500
        )

        assert progress.percent == 50.0

    def test_percent_zero_total(self):
        """Test percent with zero total bytes"""
        progress = DownloadProgress(
            url="http://example.com/file",
            output_path="/tmp/file",
            total_bytes=0,
            downloaded_bytes=100
        )

        assert progress.percent == 0.0

    def test_speed_conversion(self):
        """Test speed conversion to Mbps"""
        progress = DownloadProgress(
            url="http://example.com/file",
            output_path="/tmp/file",
            speed_bps=1024 * 1024  # 1 MB/s
        )

        assert progress.speed_mbps == 1.0

    def test_to_dict(self):
        """Test dictionary conversion"""
        progress = DownloadProgress(
            url="http://example.com/file",
            output_path="/tmp/file",
            total_bytes=1000,
            downloaded_bytes=500,
            status="downloading"
        )

        data = progress.to_dict()

        assert data["url"] == "http://example.com/file"
        assert data["total_bytes"] == 1000
        assert data["percent"] == 50.0
        assert data["status"] == "downloading"


class TestProgressTracker:
    """Test ProgressTracker"""

    @pytest.mark.asyncio
    async def test_update_progress(self):
        """Test progress update"""
        tracker = ProgressTracker(
            url="http://example.com/file",
            output_path="/tmp/file",
            total_bytes=1000
        )

        await tracker.update(500)

        assert tracker.progress.downloaded_bytes == 500
        assert tracker.progress.status == "downloading"

    @pytest.mark.asyncio
    async def test_callback_invocation(self):
        """Test that callback is called on update"""
        callback_calls = []

        def callback(progress):
            callback_calls.append(progress)

        tracker = ProgressTracker(
            url="http://example.com/file",
            output_path="/tmp/file",
            total_bytes=1000,
            callback=callback,
            update_interval=0  # Disable throttling for test
        )

        await tracker.update(500)
        await tracker.update(500)

        # Callbacks should have been called
        assert len(callback_calls) >= 1

    def test_complete_success(self):
        """Test marking download as complete"""
        tracker = ProgressTracker(
            url="http://example.com/file",
            output_path="/tmp/file",
            total_bytes=1000
        )

        tracker.complete(success=True)

        assert tracker.progress.status == "completed"

    def test_complete_failure(self):
        """Test marking download as failed"""
        tracker = ProgressTracker(
            url="http://example.com/file",
            output_path="/tmp/file",
            total_bytes=1000
        )

        tracker.complete(success=False)

        assert tracker.progress.status == "failed"


# =============================================================================
# ResultCache Tests
# =============================================================================

class TestResultCache:
    """Test ResultCache LRU caching"""

    def test_set_and_get(self):
        """Test basic cache set and get"""
        cache = ResultCache(max_size=10, ttl_seconds=60)

        cache.set("tool", {"param": "value"}, "result")
        result = cache.get("tool", {"param": "value"})

        assert result == "result"

    def test_get_miss(self):
        """Test cache miss returns None"""
        cache = ResultCache(max_size=10, ttl_seconds=60)

        result = cache.get("tool", {"param": "value"})

        assert result is None

    def test_ttl_expiration(self):
        """Test that expired entries are removed"""
        cache = ResultCache(max_size=10, ttl_seconds=1)

        cache.set("tool", {"param": "value"}, "result")

        # Wait for TTL to expire
        time.sleep(1.1)

        result = cache.get("tool", {"param": "value"})
        assert result is None

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full"""
        cache = ResultCache(max_size=2, ttl_seconds=60)

        cache.set("tool", {"param": "1"}, "result1")
        cache.set("tool", {"param": "2"}, "result2")

        # Access first entry to make it recently used
        cache.get("tool", {"param": "1"})

        # Add third entry, should evict second (least recently used)
        cache.set("tool", {"param": "3"}, "result3")

        # First entry should still exist (recently used)
        assert cache.get("tool", {"param": "1"}) == "result1"

        # Third entry should exist (just added)
        assert cache.get("tool", {"param": "3"}) == "result3"

    def test_disabled_cache(self):
        """Test that disabled cache always returns None"""
        cache = ResultCache(max_size=10, ttl_seconds=60, enabled=False)

        cache.set("tool", {"param": "value"}, "result")
        result = cache.get("tool", {"param": "value"})

        assert result is None

    def test_invalidate_specific(self):
        """Test invalidating specific cache entry"""
        cache = ResultCache(max_size=10, ttl_seconds=60)

        cache.set("tool", {"param": "1"}, "result1")
        cache.set("tool", {"param": "2"}, "result2")

        cache.invalidate("tool", {"param": "1"})

        assert cache.get("tool", {"param": "1"}) is None
        assert cache.get("tool", {"param": "2"}) == "result2"

    def test_clear(self):
        """Test clearing all cache entries"""
        cache = ResultCache(max_size=10, ttl_seconds=60)

        cache.set("tool1", {}, "result1")
        cache.set("tool2", {}, "result2")

        cache.clear()

        assert cache.get("tool1", {}) is None
        assert cache.get("tool2", {}) is None

    def test_statistics(self):
        """Test cache statistics"""
        cache = ResultCache(max_size=10, ttl_seconds=60)

        # Generate some hits and misses
        cache.set("tool", {"param": "value"}, "result")
        cache.get("tool", {"param": "value"})  # Hit
        cache.get("tool", {"param": "miss"})   # Miss
        cache.get("tool", {"param": "value"})  # Hit

        stats = cache.get_stats()

        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1
        assert stats["hit_rate_percent"] > 60


class TestGlobalCache:
    """Test global cache functions"""

    def test_get_cache_singleton(self):
        """Test that get_cache returns singleton"""
        reset_cache()

        cache1 = get_cache()
        cache2 = get_cache()

        assert cache1 is cache2

        reset_cache()

    def test_reset_cache(self):
        """Test cache reset"""
        cache = get_cache()
        cache.set("tool", {}, "result")

        reset_cache()

        new_cache = get_cache()
        assert new_cache.get("tool", {}) is None


# =============================================================================
# Integration Tests
# =============================================================================

class TestPerformanceIntegration:
    """Integration tests for performance features"""

    @pytest.mark.asyncio
    async def test_http_request_with_cache(self):
        """Test HTTP request tool with caching"""
        from app.tools.web_tools import HttpRequestTool
        from app.tools.performance import reset_cache

        reset_cache()

        tool = HttpRequestTool(use_cache=True)

        # Mock the connection pool
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.reason = "OK"
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = AsyncMock(return_value='{"key": "value"}')

        mock_session = AsyncMock()
        mock_session.request = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None)
        ))

        with patch.object(ConnectionPool, 'get_instance') as mock_pool:
            mock_pool_instance = AsyncMock()
            mock_pool_instance.get_session = MagicMock(return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_session),
                __aexit__=AsyncMock(return_value=None)
            ))
            mock_pool.return_value = mock_pool_instance

            # First request - should hit network
            result1 = await tool.execute(url="http://api.example.com/data")
            assert result1.success is True

            # Second request - should hit cache
            cache = get_cache()
            cached = cache.get("http_request", {
                "url": "http://api.example.com/data",
                "method": "GET",
                "headers": {}
            })
            assert cached is not None

        reset_cache()
        await ConnectionPool.reset_instance()

    def test_progress_tracker_full_download(self):
        """Test progress tracker for full download simulation"""
        progress_updates = []

        def callback(progress):
            progress_updates.append(progress.to_dict())

        tracker = ProgressTracker(
            url="http://example.com/file.zip",
            output_path="/tmp/file.zip",
            total_bytes=10000,
            callback=callback,
            update_interval=0  # Disable throttling
        )

        # Simulate download chunks
        async def simulate_download():
            for _ in range(10):
                await tracker.update(1000)
                await asyncio.sleep(0.01)

            tracker.complete(success=True)

        asyncio.get_event_loop().run_until_complete(simulate_download())

        # Verify final state
        assert tracker.progress.status == "completed"
        assert tracker.progress.downloaded_bytes == 10000
        assert len(progress_updates) > 0
