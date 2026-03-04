"""Tests for the chat endpoint."""

from __future__ import annotations

import pytest


class TestChatEndpoint:
    """Tests for POST /chat."""

    def test_chat_requires_api_key(self, client):
        """Request without API key should return 401."""
        response = client.post("/chat", json={"question": "Hello"})
        assert response.status_code == 401

    def test_chat_empty_question_rejected(self, client, auth_headers):
        """Empty question should be rejected by Pydantic validation."""
        response = client.post(
            "/chat",
            json={"question": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422  # Pydantic validation error
