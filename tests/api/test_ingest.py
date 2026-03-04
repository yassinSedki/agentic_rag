"""Tests for the ingest endpoint."""

from __future__ import annotations

import pytest


class TestIngestEndpoint:
    """Tests for POST /ingest."""

    def test_ingest_requires_api_key(self, client):
        """Request without API key should return 401."""
        response = client.post(
            "/ingest",
            json={"text": "test content"},
        )
        assert response.status_code == 401

    def test_ingest_empty_body(self, client, auth_headers):
        """Request with no text or content should fail."""
        response = client.post(
            "/ingest",
            json={},
            headers=auth_headers,
        )
        # Should be rejected because neither text nor content_base64 is provided
        assert response.status_code in (422, 500)
