"""Tests for agent tools."""

from __future__ import annotations

import pytest

from app.agent.tools.memory_store import retrieve_context, store_summary


class TestMemoryStoreStub:
    """Test the memory store stub (should be no-ops)."""

    @pytest.mark.asyncio
    async def test_store_summary_stub(self):
        result = await store_summary("conv-1", "test summary")
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_retrieve_context_stub(self):
        result = await retrieve_context("conv-1")
        assert result == ""
