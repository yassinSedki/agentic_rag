"""SQLite-backed persistent memory store for conversation history.

This module provides a lightweight MemoryStore that persists chat
turns to a local SQLite database, allowing the backend to load history
even if the client drops it.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import structlog

from app.core.config import get_settings

logger = structlog.get_logger()


class MemoryStore:
    """A simple SQLite-backed memory store for conversation turns."""

    def __init__(self, db_path: str = "data/chat_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database schema if it doesn't exist."""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_conversation_id ON memory(conversation_id)'
            )
            conn.commit()

    def get_history(
        self, conversation_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Retrieve recent conversation history for a given session.

        Parameters
        ----------
        conversation_id : str
            The unique identifier for the conversation.
        limit : int, optional
            The maximum number of **messages** to return. Note that a full turn
            is 2 messages (user + ai), so limit=10 returns the last 5 turns.

        Returns
        -------
        list[dict[str, Any]]
            A list of message dictionaries e.g. [{"role": "user", "content": "..."}]
        """
        settings = get_settings()
        if not settings.enable_memory:
            return []

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Fetch recent messages ordered by latest first
                cursor.execute(
                    '''
                    SELECT role, content FROM memory 
                    WHERE conversation_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                    ''',
                    (conversation_id, limit),
                )
                rows = cursor.fetchall()
                # Reverse to chronological order
                return [{"role": row[0], "content": row[1]} for row in reversed(rows)]
        except Exception as e:
            logger.error("memory_get_error", error=str(e), conversation_id=conversation_id)
            return []

    def save_turn(self, conversation_id: str, user_message: str, ai_message: str) -> None:
        """Save a single back-and-forth turn to the memory store.

        Parameters
        ----------
        conversation_id : str
            The session identifier.
        user_message : str
            The text the user asked.
        ai_message : str
            The generated response from the agent.
        """
        settings = get_settings()
        if not settings.enable_memory:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO memory (conversation_id, role, content) VALUES (?, ?, ?)',
                    (conversation_id, "user", user_message),
                )
                cursor.execute(
                    'INSERT INTO memory (conversation_id, role, content) VALUES (?, ?, ?)',
                    (conversation_id, "ai", ai_message),
                )
                conn.commit()
            logger.info("memory_saved_turn", conversation_id=conversation_id)
        except Exception as e:
            logger.error("memory_save_error", error=str(e), conversation_id=conversation_id)


# Global singleton instance for the app
_memory_store = MemoryStore()

def get_memory_store() -> MemoryStore:
    """Return the global MemoryStore instance."""
    return _memory_store
