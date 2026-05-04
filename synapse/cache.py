"""Search result cache — LRU + TTL eviction.

Caches hybrid search results keyed by (query, scope, mode).
Entries expire after cache_ttl seconds or when evicted by LRU policy.
"""

import logging
import time
from collections import OrderedDict
from typing import Optional

log = logging.getLogger("synapse.cache")


class SearchCache:
    """LRU + TTL cache for search results.

    Args:
        max_size: Maximum number of entries (LRU eviction when exceeded).
        ttl: Time-to-live in seconds (entries expire after this).
    """

    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self._max_size = max_size
        self._ttl = ttl
        self._cache: OrderedDict[str, tuple] = OrderedDict()  # key -> (results, timestamp)

    def _make_key(self, query: str, scope: Optional[str], mode: str, limit: int) -> str:
        """Create cache key from search parameters."""
        scope_str = scope or "*"
        return f"{query}||{scope_str}||{mode}||{limit}"

    def get(self, query: str, scope: Optional[str] = None, mode: str = "hybrid", limit: int = 10) -> Optional[list]:
        """Get cached search results if still valid.

        Returns None if not cached or expired.
        """
        key = self._make_key(query, scope, mode, limit)
        if key not in self._cache:
            return None

        results, timestamp = self._cache[key]

        # Check TTL
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            log.debug("Cache expired: %s", key[:50])
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        return results

    def put(self, query: str, results: list, scope: Optional[str] = None, mode: str = "hybrid", limit: int = 10) -> None:
        """Cache search results."""
        key = self._make_key(query, scope, mode, limit)

        if key in self._cache:
            self._cache.move_to_end(key)

        self._cache[key] = (results, time.time())

        # Evict oldest if over max size
        while len(self._cache) > self._max_size:
            evicted_key, _ = self._cache.popitem(last=False)
            log.debug("Cache evicted (LRU): %s", evicted_key[:50])

    def invalidate(self, query: Optional[str] = None, scope: Optional[str] = None) -> int:
        """Invalidate cache entries.

        Args:
            query: If provided, invalidate entries matching this query.
            scope: If provided, invalidate entries matching this scope.

        Returns:
            Number of entries invalidated.
        """
        if query is None and scope is None:
            # Clear entire cache
            count = len(self._cache)
            self._cache.clear()
            log.info("Cache cleared: %d entries", count)
            return count

        keys_to_remove = []
        scope_str = scope or "*"

        for key in self._cache:
            parts = key.split("||")
            if len(parts) != 4:
                continue
            cached_query, cached_scope, cached_mode, cached_limit = parts

            if query and cached_query != query:
                continue
            if scope and cached_scope != scope_str:
                continue

            keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._cache[key]

        log.info("Cache invalidated: %d entries removed", len(keys_to_remove))
        return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    @property
    def size(self) -> int:
        """Current number of cached entries."""
        return len(self._cache)

    def stats(self) -> dict:
        """Cache statistics."""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "ttl": self._ttl,
        }