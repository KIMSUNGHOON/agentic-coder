"""LM Cache service for caching LLM responses."""
import os
import json
import hashlib
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Data directory for file-based cache
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
CACHE_DIR = os.path.join(DATA_DIR, "lm_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


@dataclass
class CacheEntry:
    """Cache entry for LLM response."""
    key: str
    response: str
    model: str
    prompt_hash: str
    created_at: str
    expires_at: str
    hit_count: int = 0
    metadata: Optional[Dict[str, Any]] = None


class LMCacheService:
    """Cache service for LLM responses.

    Supports both Redis (if available) and file-based caching.
    Uses semantic similarity for cache matching when vector_db is enabled.
    """

    def __init__(
        self,
        ttl_hours: int = 24,
        use_redis: bool = True,
        redis_url: str = "redis://localhost:6379"
    ):
        """Initialize LM Cache service.

        Args:
            ttl_hours: Time-to-live for cache entries in hours
            use_redis: Whether to try using Redis
            redis_url: Redis connection URL
        """
        self.ttl_hours = ttl_hours
        self.redis_url = redis_url
        self._redis_client = None
        self._use_redis = use_redis
        self._redis_available = False

        if use_redis:
            self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection."""
        try:
            import redis
            self._redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True
            )
            # Test connection
            self._redis_client.ping()
            self._redis_available = True
            logger.info("Connected to Redis for LM caching")
        except ImportError:
            logger.info("Redis not installed, using file-based cache")
            self._redis_available = False
        except Exception as e:
            logger.warning(f"Redis not available: {e}. Using file-based cache")
            self._redis_available = False

    def _generate_key(self, prompt: str, model: str, **kwargs) -> str:
        """Generate cache key from prompt and parameters.

        Args:
            prompt: The LLM prompt
            model: Model name
            **kwargs: Additional parameters to include in key

        Returns:
            Cache key string
        """
        # Create deterministic hash from prompt and key parameters
        key_data = {
            "prompt": prompt,
            "model": model,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def _get_file_path(self, key: str) -> str:
        """Get file path for cache entry."""
        return os.path.join(CACHE_DIR, f"{key}.json")

    def get(self, prompt: str, model: str, **kwargs) -> Optional[str]:
        """Get cached response for prompt.

        Args:
            prompt: The LLM prompt
            model: Model name
            **kwargs: Additional parameters

        Returns:
            Cached response or None
        """
        key = self._generate_key(prompt, model, **kwargs)

        if self._redis_available:
            return self._get_redis(key)
        else:
            return self._get_file(key)

    def _get_redis(self, key: str) -> Optional[str]:
        """Get from Redis cache."""
        try:
            data = self._redis_client.get(f"lm_cache:{key}")
            if data:
                entry = json.loads(data)
                # Update hit count
                entry["hit_count"] = entry.get("hit_count", 0) + 1
                self._redis_client.set(
                    f"lm_cache:{key}",
                    json.dumps(entry),
                    ex=int(self.ttl_hours * 3600)
                )
                logger.debug(f"Cache hit (Redis): {key[:16]}...")
                return entry["response"]
        except Exception as e:
            logger.error(f"Redis get error: {e}")
        return None

    def _get_file(self, key: str) -> Optional[str]:
        """Get from file cache."""
        file_path = self._get_file_path(key)
        try:
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    entry = json.load(f)

                # Check expiration
                expires_at = datetime.fromisoformat(entry["expires_at"])
                if datetime.utcnow() > expires_at:
                    os.remove(file_path)
                    return None

                # Update hit count
                entry["hit_count"] = entry.get("hit_count", 0) + 1
                with open(file_path, "w") as f:
                    json.dump(entry, f)

                logger.debug(f"Cache hit (file): {key[:16]}...")
                return entry["response"]
        except Exception as e:
            logger.error(f"File cache get error: {e}")
        return None

    def set(
        self,
        prompt: str,
        response: str,
        model: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """Cache LLM response.

        Args:
            prompt: The LLM prompt
            response: The LLM response
            model: Model name
            metadata: Optional metadata
            **kwargs: Additional parameters

        Returns:
            Cache key
        """
        key = self._generate_key(prompt, model, **kwargs)

        entry = CacheEntry(
            key=key,
            response=response,
            model=model,
            prompt_hash=hashlib.md5(prompt.encode()).hexdigest(),
            created_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(hours=self.ttl_hours)).isoformat(),
            hit_count=0,
            metadata=metadata
        )

        if self._redis_available:
            self._set_redis(key, entry)
        else:
            self._set_file(key, entry)

        return key

    def _set_redis(self, key: str, entry: CacheEntry) -> None:
        """Set in Redis cache."""
        try:
            self._redis_client.set(
                f"lm_cache:{key}",
                json.dumps(asdict(entry)),
                ex=int(self.ttl_hours * 3600)
            )
            logger.debug(f"Cached (Redis): {key[:16]}...")
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    def _set_file(self, key: str, entry: CacheEntry) -> None:
        """Set in file cache."""
        file_path = self._get_file_path(key)
        try:
            with open(file_path, "w") as f:
                json.dump(asdict(entry), f)
            logger.debug(f"Cached (file): {key[:16]}...")
        except Exception as e:
            logger.error(f"File cache set error: {e}")

    def delete(self, prompt: str, model: str, **kwargs) -> bool:
        """Delete cached entry.

        Args:
            prompt: The LLM prompt
            model: Model name
            **kwargs: Additional parameters

        Returns:
            True if deleted
        """
        key = self._generate_key(prompt, model, **kwargs)

        if self._redis_available:
            try:
                return bool(self._redis_client.delete(f"lm_cache:{key}"))
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
                return False
        else:
            file_path = self._get_file_path(key)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    return True
            except Exception as e:
                logger.error(f"File cache delete error: {e}")
            return False

    def clear(self) -> int:
        """Clear all cached entries.

        Returns:
            Number of entries cleared
        """
        count = 0

        if self._redis_available:
            try:
                keys = self._redis_client.keys("lm_cache:*")
                if keys:
                    count = self._redis_client.delete(*keys)
                logger.info(f"Cleared {count} Redis cache entries")
            except Exception as e:
                logger.error(f"Redis clear error: {e}")
        else:
            try:
                for filename in os.listdir(CACHE_DIR):
                    if filename.endswith(".json"):
                        os.remove(os.path.join(CACHE_DIR, filename))
                        count += 1
                logger.info(f"Cleared {count} file cache entries")
            except Exception as e:
                logger.error(f"File cache clear error: {e}")

        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with stats
        """
        stats = {
            "backend": "redis" if self._redis_available else "file",
            "ttl_hours": self.ttl_hours,
            "cache_dir": CACHE_DIR,
        }

        if self._redis_available:
            try:
                keys = self._redis_client.keys("lm_cache:*")
                stats["entry_count"] = len(keys)

                # Get memory info
                info = self._redis_client.info("memory")
                stats["used_memory"] = info.get("used_memory_human", "unknown")
            except Exception as e:
                stats["error"] = str(e)
        else:
            try:
                files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")]
                stats["entry_count"] = len(files)

                # Get total size
                total_size = sum(
                    os.path.getsize(os.path.join(CACHE_DIR, f))
                    for f in files
                )
                stats["total_size_bytes"] = total_size
            except Exception as e:
                stats["error"] = str(e)

        return stats

    def cleanup_expired(self) -> int:
        """Remove expired cache entries (file-based only).

        Returns:
            Number of entries removed
        """
        if self._redis_available:
            # Redis handles expiration automatically
            return 0

        count = 0
        try:
            for filename in os.listdir(CACHE_DIR):
                if not filename.endswith(".json"):
                    continue

                file_path = os.path.join(CACHE_DIR, filename)
                try:
                    with open(file_path, "r") as f:
                        entry = json.load(f)

                    expires_at = datetime.fromisoformat(entry["expires_at"])
                    if datetime.utcnow() > expires_at:
                        os.remove(file_path)
                        count += 1
                except Exception:
                    pass  # Skip invalid files

            logger.info(f"Cleaned up {count} expired cache entries")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

        return count


# Global instance
lm_cache = LMCacheService()
