"""Shared fixtures for Synapse tests."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from synapse.store.sqlite_store import SQLiteStore


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a temporary .synapse/ vault directory."""
    vault = tmp_path / ".synapse"
    vault.mkdir()
    return vault


@pytest.fixture
def sqlite_store(tmp_vault):
    """Create a SQLiteStore backed by a temp vault."""
    store = SQLiteStore(tmp_vault)
    yield store
    store.close()


@pytest.fixture
def populated_vault(sqlite_store):
    """SQLiteStore with a few sample documents."""
    sqlite_store.add("Python Tips", "Use list comprehensions for filtering", scope="shared", doc_type="learning")
    sqlite_store.add("Git Workflow", "Rebase vs merge: prefer rebase for clean history", scope="shared", doc_type="pattern")
    sqlite_store.add("React Hooks", "Use useEffect for side effects, useState for local state", scope="frontend", doc_type="learning")
    return sqlite_store


def mock_embed_response(vectors=None, dim=768):
    """Create a mock httpx response for Ollama embedding API."""
    if vectors is None:
        import random
        vectors = [random.uniform(-0.1, 0.1) for _ in range(dim)]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"embeddings": [vectors]}
    return mock_resp


@pytest.fixture
def mock_ollama():
    """Mock httpx.post to simulate Ollama embedding API."""
    with patch("httpx.post", return_value=mock_embed_response()) as mock_post:
        yield mock_post


@pytest.fixture
def mock_ollama_timeout():
    """Mock httpx.post to simulate Ollama timeout."""
    import httpx
    with patch("httpx.post", side_effect=httpx.TimeoutException("timeout")) as mock_post:
        yield mock_post


@pytest.fixture
def mock_ollama_error():
    """Mock httpx.post to simulate Ollama HTTP error."""
    import httpx
    with patch("httpx.post", side_effect=httpx.HTTPError("connection failed")) as mock_post:
        yield mock_post