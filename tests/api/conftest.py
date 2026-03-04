"""API test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    """Return a FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Return headers with a valid test API key."""
    return {"X-API-Key": "changeme"}
