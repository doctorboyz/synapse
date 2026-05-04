"""Tests for synapse.cache — SearchCache LRU + TTL."""

import time

import pytest

from synapse.cache import SearchCache


class TestSearchCachePutGet:
    def test_put_and_get(self):
        cache = SearchCache(max_size=10, ttl=300)
        cache.put("python", [{"id": "1", "title": "Python Tips"}])
        result = cache.get("python")
        assert result is not None
        assert result[0]["title"] == "Python Tips"

    def test_get_miss(self):
        cache = SearchCache(max_size=10, ttl=300)
        result = cache.get("nonexistent")
        assert result is None

    def test_get_with_scope(self):
        cache = SearchCache(max_size=10, ttl=300)
        cache.put("python", [{"id": "1"}], scope="shared")
        assert cache.get("python", scope="shared") is not None
        assert cache.get("python", scope="other") is None

    def test_get_with_mode(self):
        cache = SearchCache(max_size=10, ttl=300)
        cache.put("python", [{"id": "1"}], mode="hybrid")
        assert cache.get("python", mode="hybrid") is not None
        assert cache.get("python", mode="fts") is None

    def test_get_with_limit(self):
        cache = SearchCache(max_size=10, ttl=300)
        cache.put("python", [{"id": "1"}], limit=10)
        assert cache.get("python", limit=10) is not None
        assert cache.get("python", limit=5) is None


class TestSearchCacheTTL:
    def test_expired_entry(self):
        cache = SearchCache(max_size=10, ttl=1)  # 1 second TTL
        cache.put("python", [{"id": "1"}])
        # Immediately available
        assert cache.get("python") is not None
        # Wait for expiry
        time.sleep(1.5)
        assert cache.get("python") is None

    def test_not_expired_entry(self):
        cache = SearchCache(max_size=10, ttl=300)
        cache.put("python", [{"id": "1"}])
        assert cache.get("python") is not None


class TestSearchCacheLRU:
    def test_eviction_when_over_max_size(self):
        cache = SearchCache(max_size=3, ttl=300)
        cache.put("query1", [{"id": "1"}])
        cache.put("query2", [{"id": "2"}])
        cache.put("query3", [{"id": "3"}])
        cache.put("query4", [{"id": "4"}])  # Should evict query1

        assert cache.get("query1") is None
        assert cache.get("query4") is not None

    def test_lru_promotion(self):
        cache = SearchCache(max_size=3, ttl=300)
        cache.put("query1", [{"id": "1"}])
        cache.put("query2", [{"id": "2"}])
        cache.put("query3", [{"id": "3"}])

        # Access query1 to promote it
        cache.get("query1")

        # Adding query4 should evict query2 (oldest unused)
        cache.put("query4", [{"id": "4"}])
        assert cache.get("query1") is not None  # Still cached (promoted)
        assert cache.get("query2") is None  # Evicted


class TestSearchCacheInvalidation:
    def test_invalidate_all(self):
        cache = SearchCache(max_size=10, ttl=300)
        cache.put("python", [{"id": "1"}])
        cache.put("docker", [{"id": "2"}])
        count = cache.invalidate()
        assert count == 2
        assert cache.size == 0

    def test_invalidate_by_scope(self):
        cache = SearchCache(max_size=10, ttl=300)
        cache.put("python", [{"id": "1"}], scope="shared")
        cache.put("python", [{"id": "2"}], scope="project-a")
        cache.put("docker", [{"id": "3"}], scope="shared")
        count = cache.invalidate(scope="shared")
        assert count == 2
        assert cache.get("python", scope="project-a") is not None

    def test_invalidate_by_query(self):
        cache = SearchCache(max_size=10, ttl=300)
        cache.put("python", [{"id": "1"}])
        cache.put("docker", [{"id": "2"}])
        count = cache.invalidate(query="python")
        assert count == 1
        assert cache.get("python") is None
        assert cache.get("docker") is not None


class TestSearchCacheStats:
    def test_stats(self):
        cache = SearchCache(max_size=100, ttl=300)
        cache.put("python", [{"id": "1"}])
        stats = cache.stats()
        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["ttl"] == 300

    def test_size_property(self):
        cache = SearchCache(max_size=10, ttl=300)
        assert cache.size == 0
        cache.put("python", [{"id": "1"}])
        assert cache.size == 1

    def test_clear(self):
        cache = SearchCache(max_size=10, ttl=300)
        cache.put("python", [{"id": "1"}])
        cache.put("docker", [{"id": "2"}])
        cache.clear()
        assert cache.size == 0