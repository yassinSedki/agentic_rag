"""Tests for the persistent MemoryStore."""

from __future__ import annotations

import os
import sqlite3
import pytest

from app.agent.memory.store import MemoryStore


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database file for testing."""
    db_file = tmp_path / "test_memory.db"
    return str(db_file)


class TestMemoryStore:
    """Tests for SQLite memory persistence."""

    def test_init_creates_table(self, temp_db):
        store = MemoryStore(db_path=temp_db)
        # Check if table exists
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_history'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_save_and_get_history(self, temp_db):
        store = MemoryStore(db_path=temp_db)
        conv_id = "test-123"
        
        store.save_turn(conv_id, "Hello", "Hi there!")
        store.save_turn(conv_id, "How are you?", "I am good.")
        
        history = store.get_history(conv_id)
        assert len(history) == 4  # 2 turns * (user + assistant)
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hi there!"

    def test_get_history_empty(self, temp_db):
        store = MemoryStore(db_path=temp_db)
        assert store.get_history("nonexistent") == []

    def test_limit_history(self, temp_db):
        store = MemoryStore(db_path=temp_db)
        conv_id = "limit-test"
        
        # Save 10 turns
        for i in range(10):
            store.save_turn(conv_id, f"Q{i}", f"A{i}")
            
        history = store.get_history(conv_id, limit=5)
        assert len(history) == 10  # limit is on turns, so 5 turns = 10 messages
        
        # Verify it gets the LATEST turns (Q5-Q9)
        assert "Q5" in history[0]["content"]
        assert "Q9" in history[-2]["content"]
