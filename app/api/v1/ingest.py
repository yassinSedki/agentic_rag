"""Ingest endpoint — accept documents and push into the vector store.

POST /ingest accepts raw text, file content (base64), or references
and delegates to the ``DocumentProcessor`` pipeline.
"""

from __future__ import annotations

import base64
import tempfile
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends

from app.api.v1.models.ingest import IngestRequest, IngestResponse
from app.core.config import get_settings
from app.core.exceptions import IngestError
from app.core.metrics import REQUEST_COUNT
from app.core.security import verify_api_key
from app.ingest.document_processor import DocumentProcessor
from app.vectorstore.chroma import ChromaAdapter

logger = structlog.get_logger()

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    body: IngestRequest,
    api_key: str = Depends(verify_api_key),
) -> IngestResponse:
    """Ingest a document into the knowledge base.

    Accepts raw text, base64-encoded file content, or both.
    """
    logger.info(
        "ingest_request",
        filename=body.filename,
        has_text=body.text is not None,
        has_base64=body.content_base64 is not None,
    )

    try:
        vector_store = ChromaAdapter()
        processor = DocumentProcessor(vector_store)

        if body.content_base64:
            # Decode base64 content and write to temp file
            decoded = base64.b64decode(body.content_base64)
            suffix = Path(body.filename).suffix if body.filename else ".txt"

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=suffix
            ) as tmp:
                tmp.write(decoded)
                tmp_path = tmp.name

            result = await processor.process(
                source=tmp_path,
                filename=body.filename,
                metadata=body.metadata,
            )
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

        elif body.text:
            result = await processor.process(
                source=body.text,
                filename=body.filename or "raw_text",
                metadata=body.metadata,
            )
        else:
            raise IngestError("Either 'text' or 'content_base64' must be provided.")

        REQUEST_COUNT.labels(endpoint="/ingest", status="success").inc()

        return IngestResponse(
            doc_ids=result["doc_ids"],
            chunks_created=result["chunks_created"],
            status=result["status"],
        )

    except IngestError:
        raise
    except Exception as exc:
        logger.error("ingest_failed", error=str(exc))
        REQUEST_COUNT.labels(endpoint="/ingest", status="error").inc()
        raise IngestError(f"Ingestion failed: {exc}") from exc
