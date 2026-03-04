"""Tests for the circuit breaker."""

from __future__ import annotations

import pytest

from app.core.circuit_breaker import CircuitBreaker, State
from app.core.exceptions import CircuitOpenError


class TestCircuitBreaker:
    """Tests for circuit breaker state transitions."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        cb = CircuitBreaker(service="test", threshold=3, reset_s=10)
        assert cb.state == State.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        cb = CircuitBreaker(service="test", threshold=2, reset_s=10)

        async def failing():
            raise ValueError("fail")

        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(failing)

        assert cb.state == State.OPEN

    @pytest.mark.asyncio
    async def test_rejects_when_open(self):
        cb = CircuitBreaker(service="test", threshold=1, reset_s=300)

        async def failing():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            await cb.call(failing)

        assert cb.state == State.OPEN

        with pytest.raises(CircuitOpenError):
            await cb.call(failing)

    @pytest.mark.asyncio
    async def test_success_resets(self):
        cb = CircuitBreaker(service="test", threshold=5, reset_s=10)

        async def failing():
            raise ValueError("fail")

        async def succeeding():
            return "ok"

        # One failure, then success
        with pytest.raises(ValueError):
            await cb.call(failing)

        result = await cb.call(succeeding)
        assert result == "ok"
        assert cb.state == State.CLOSED
