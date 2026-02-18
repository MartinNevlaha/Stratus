"""Tests for retrieval/embed_cache.py — TDD RED phase first."""

from __future__ import annotations

from stratus.retrieval.embed_cache import EmbedCache, compute_content_hash


def test_compute_content_hash_deterministic() -> None:
    """Same content + model always yields same hash."""
    h1 = compute_content_hash("hello world", "nomic-embed-text-v1.5")
    h2 = compute_content_hash("hello world", "nomic-embed-text-v1.5")
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex

def test_compute_content_hash_different_for_different_model() -> None:
    """Same content with different model yields different hash."""
    h1 = compute_content_hash("hello world", "model-a")
    h2 = compute_content_hash("hello world", "model-b")
    assert h1 != h2

def test_has_returns_false_for_missing() -> None:
    """has() returns False for a hash not in the cache."""
    cache = EmbedCache(":memory:")
    assert cache.has("nonexistent") is False
    cache.close()

def test_put_and_has() -> None:
    """After put(), has() returns True for that hash."""
    cache = EmbedCache(":memory:")
    h = compute_content_hash("some code", "test-model")
    cache.put(h, "src/foo.py", 0, "test-model")
    assert cache.has(h) is True
    cache.close()

def test_put_and_get() -> None:
    """get() returns the stored row as a dict with correct fields."""
    cache = EmbedCache(":memory:")
    h = compute_content_hash("some code", "test-model")
    cache.put(h, "src/foo.py", 2, "test-model")

    result = cache.get(h)

    assert result is not None
    assert result["content_hash"] == h
    assert result["file_path"] == "src/foo.py"
    assert result["chunk_index"] == 2
    assert result["model_name"] == "test-model"
    cache.close()

def test_get_returns_none_for_missing() -> None:
    """get() returns None for unknown hash."""
    cache = EmbedCache(":memory:")
    assert cache.get("nope") is None
    cache.close()

def test_get_increments_hit_count() -> None:
    """Each get() call increments hit_count."""
    cache = EmbedCache(":memory:")
    h = compute_content_hash("data", "model")
    cache.put(h, "file.py", 0, "model")

    cache.get(h)
    cache.get(h)
    result = cache.get(h)

    assert result is not None
    assert result["hit_count"] == 3
    cache.close()

def test_invalidate_removes_by_file_path() -> None:
    """invalidate() removes all entries for the given file_path."""
    cache = EmbedCache(":memory:")
    h1 = compute_content_hash("chunk1", "model")
    h2 = compute_content_hash("chunk2", "model")
    h3 = compute_content_hash("other", "model")

    cache.put(h1, "src/target.py", 0, "model")
    cache.put(h2, "src/target.py", 1, "model")
    cache.put(h3, "src/other.py", 0, "model")

    cache.invalidate("src/target.py")

    assert cache.has(h1) is False
    assert cache.has(h2) is False
    assert cache.has(h3) is True
    cache.close()

def test_invalidate_returns_count() -> None:
    """invalidate() returns the number of deleted rows."""
    cache = EmbedCache(":memory:")
    h1 = compute_content_hash("chunk1", "model")
    h2 = compute_content_hash("chunk2", "model")

    cache.put(h1, "src/target.py", 0, "model")
    cache.put(h2, "src/target.py", 1, "model")

    count = cache.invalidate("src/target.py")

    assert count == 2
    cache.close()

def test_stats_empty() -> None:
    """stats() returns zeros for an empty cache."""
    cache = EmbedCache(":memory:")
    s = cache.stats()
    assert s["total_entries"] == 0
    assert s["total_hits"] == 0
    assert s["models"] == []
    cache.close()

def test_stats_with_data() -> None:
    """stats() returns correct counts after inserts and gets."""
    cache = EmbedCache(":memory:")
    h1 = compute_content_hash("a", "model-x")
    h2 = compute_content_hash("b", "model-y")

    cache.put(h1, "f1.py", 0, "model-x")
    cache.put(h2, "f2.py", 0, "model-y")
    cache.get(h1)
    cache.get(h1)

    s = cache.stats()
    assert s["total_entries"] == 2
    assert s["total_hits"] == 2
    assert set(s["models"]) == {"model-x", "model-y"}
    cache.close()

def test_prune_old_entries() -> None:
    """prune() deletes entries older than specified days and returns count."""
    cache = EmbedCache(":memory:")

    # Insert an entry with a very old cached_at timestamp
    cache._conn.execute(
        """INSERT INTO embed_cache
           (content_hash, file_path, chunk_index, model_name, cached_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("oldhash", "old.py", 0, "model", "2020-01-01T00:00:00.000Z"),
    )
    cache._conn.commit()

    # Insert a fresh entry via normal put
    h = compute_content_hash("fresh", "model")
    cache.put(h, "fresh.py", 0, "model")

    deleted = cache.prune(older_than_days=30)

    assert deleted == 1
    assert cache.has("oldhash") is False
    assert cache.has(h) is True
    cache.close()

def test_close() -> None:
    """close() can be called without error."""
    cache = EmbedCache(":memory:")
    cache.put(compute_content_hash("x", "m"), "f.py", 0, "m")
    cache.close()  # should not raise
