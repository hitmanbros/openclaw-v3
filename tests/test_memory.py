"""Tests for SQLite keyword memory."""

import pytest
import tempfile
from pathlib import Path

from openclaw.memory.store import MemoryStore


class TestMemoryStore:
    """Memory store behavior."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d) / "memory.db"

    def test_remember_stores_content(self, temp_db):
        """Remember stores content in the database."""
        store = MemoryStore(temp_db)
        store.remember("API uses FastAPI", scope="project")
        
        results = store.recall("FastAPI")
        assert len(results) == 1
        assert results[0]["content"] == "API uses FastAPI"

    def test_recall_matches_keywords(self, temp_db):
        """Recall returns entries matching query keywords."""
        store = MemoryStore(temp_db)
        store.remember("API uses FastAPI", scope="project")
        store.remember("Database uses PostgreSQL", scope="project")
        
        results = store.recall("FastAPI")
        assert len(results) == 1
        assert results[0]["content"] == "API uses FastAPI"

    def test_recall_no_match_returns_empty(self, temp_db):
        """Recall with no matches returns empty list."""
        store = MemoryStore(temp_db)
        store.remember("API uses FastAPI", scope="project")
        
        results = store.recall("Django")
        assert results == []

    def test_remember_includes_timestamp(self, temp_db):
        """Remembered entries include timestamps."""
        store = MemoryStore(temp_db)
        store.remember("Test content", scope="project")
        
        results = store.recall("Test")
        assert "created_at" in results[0]

    def test_recall_respects_limit(self, temp_db):
        """Recall limit restricts number of results."""
        store = MemoryStore(temp_db)
        for i in range(10):
            store.remember(f"Item {i}", scope="project")
        
        results = store.recall("Item", limit=3)
        assert len(results) == 3

    def test_different_scopes_are_isolated(self, temp_db):
        """Project scope doesn't see team scope entries."""
        store = MemoryStore(temp_db)
        store.remember("Project secret", scope="project")
        store.remember("Team knowledge", scope="team")
        
        project_results = store.recall("secret", scope="project")
        assert len(project_results) == 1
        
        team_results = store.recall("secret", scope="team")
        assert len(team_results) == 0

    def test_persists_across_instances(self, temp_db):
        """Data persists when store is reopened."""
        store1 = MemoryStore(temp_db)
        store1.remember("Persistent data", scope="project")
        
        store2 = MemoryStore(temp_db)
        results = store2.recall("Persistent")
        assert len(results) == 1

    def test_recall_matches_partial_words(self, temp_db):
        """Recall matches partial word in content."""
        store = MemoryStore(temp_db)
        store.remember("FastAPI router setup", scope="project")
        
        results = store.recall("router")
        assert len(results) == 1
