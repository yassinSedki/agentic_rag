"""Tests for the chat endpoint."""

from __future__ import annotations

import json
import time
from unittest.mock import patch

import pytest

from app.core.exceptions import LLMTimeoutError


class TestChatEndpoint:
    """Tests for POST /chat."""

    def test_chat_empty_question_rejected(self, client, auth_headers):
        """Empty question should be rejected by Pydantic validation."""
        response = client.post(
            "/chat",
            json={"question": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422  # Pydantic validation error

    def test_chat_stream_includes_citations_in_done_event(self, client, auth_headers):
        """If the agent returns source ids, the done event should include them."""

        class FakeGraph:
            async def ainvoke(self, state):
                return {
                    "generation_prompt": "Answer this: " + state["question"],
                    "source_ids": ["doc-1", "doc-2"],
                    "retrieval_score": 0.9,
                    "error": None,
                }

        with patch("app.api.v1.chat.build_graph", return_value=FakeGraph()):
            with client.stream(
                "POST",
                "/chat",
                json={"question": "What is the refund policy?"},
                headers=auth_headers,
            ) as response:
                assert response.status_code == 200
                assert response.headers["content-type"].startswith("text/event-stream")

                events: list[dict] = []
                for raw_line in response.iter_lines():
                    line = raw_line.decode("utf-8") if isinstance(raw_line, (bytes, bytearray)) else raw_line
                    if not line.startswith("data: "):
                        continue
                    events.append(json.loads(line[len("data: ") :]))
                    if events and events[-1].get("type") == "done":
                        break

        assert any(e.get("type") == "token" for e in events)
        done = next(e for e in events if e.get("type") == "done")
        assert [s["doc_id"] for s in done["sources"]] == ["doc-1", "doc-2"]

    def test_chat_ollama_timeout_returns_streamed_error_event(self, client, auth_headers):
        """Timeouts should be surfaced as an error SSE event (no real Ollama needed)."""

        class FakeGraph:
            async def ainvoke(self, state):
                raise LLMTimeoutError("Ollama timed out")

        with patch("app.api.v1.chat.build_graph", return_value=FakeGraph()):
            with client.stream(
                "POST",
                "/chat",
                json={"question": "Hi"},
                headers=auth_headers,
            ) as response:
                assert response.status_code == 200
                first_event = None
                for raw_line in response.iter_lines():
                    line = raw_line.decode("utf-8") if isinstance(raw_line, (bytes, bytearray)) else raw_line
                    if line.startswith("data: "):
                        first_event = json.loads(line[len("data: ") :])
                        break

        assert first_event is not None
        assert first_event["type"] == "error"
        # Implementation uses INTERNAL_ERROR for exceptions raised during graph execution
        msg = first_event["message"].lower()
        assert ("timeout" in msg) or ("timed out" in msg)

    def test_chat_stream_first_chunk_emitted_quickly_when_agent_fast(self, client, auth_headers):
        """Basic streaming behavior: first SSE chunk should arrive quickly for a fast agent."""

        class FakeGraph:
            async def ainvoke(self, state):
                return {
                    "final_answer": "A" * 500,
                    "source_ids": [],
                    "retrieval_score": 0.0,
                    "error": None,
                }

        with patch("app.api.v1.chat.build_graph", return_value=FakeGraph()):
            start = time.monotonic()
            with client.stream(
                "POST",
                "/chat",
                json={"question": "Hello"},
                headers=auth_headers,
            ) as response:
                assert response.status_code == 200
                got_token = False
                for raw_line in response.iter_lines():
                    line = raw_line.decode("utf-8") if isinstance(raw_line, (bytes, bytearray)) else raw_line
                    if not line.startswith("data: "):
                        continue
                    evt = json.loads(line[len("data: ") :])
                    if evt.get("type") == "token":
                        got_token = True
                        break

            elapsed_ms = (time.monotonic() - start) * 1000

        assert got_token is True
        # Keep threshold generous to avoid flaky CI on slower machines.
        assert elapsed_ms < 1500
