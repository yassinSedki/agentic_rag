"""Tests for the ingest endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


class TestIngestEndpoint:
    """Tests for POST /ingest."""

    def test_ingest_missing_file_rejected(self, client, auth_headers):
        """Missing required multipart file should fail validation."""
        response = client.post("/ingest", headers=auth_headers)
        assert response.status_code == 422

    def test_ingest_file_upload_success(self, client, auth_headers):
        """Uploading a file should return an ingest response (mocked pipeline)."""
        mock_vs = MagicMock()
        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(
            return_value={
                "doc_ids": ["doc-1"],
                "chunks_created": 2,
                "status": "ok",
            }
        )

        with (
            patch("app.api.v1.ingest.VectorStore", return_value=mock_vs),
            patch("app.api.v1.ingest.DocumentProcessor", return_value=mock_processor),
        ):
            files = {"file": ("policy.txt", b"Refunds within 30 days.", "text/plain")}
            response = client.post("/ingest", files=files, headers=auth_headers)

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["chunks_created"] == 2
        assert payload["doc_ids"] == ["doc-1"]
