"""Ingest endpoint — accept uploaded files and push into the vector store.

POST /ingest accepts a file upload and delegates to the
``DocumentProcessor`` pipeline. Metadata such as filename and page
number are derived automatically.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, UploadFile

from app.api.v1.models.ingest import IngestResponse
from app.core.config import get_settings
from app.core.exceptions import IngestError
from app.core.metrics import REQUEST_COUNT
from app.ingest.document_processor import DocumentProcessor
from app.vectorstore import VectorStore

logger = structlog.get_logger()

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
) -> IngestResponse:
    """Ingest a document via direct file upload.

    The client uploads a single file (PDF, TXT, MD, DOCX). The system
    derives metadata automatically:

    - ``source``: original filename.
    - ``page``: for PDFs, each page becomes a separate ``Document`` with
      its own page number.

    No user-supplied metadata is required; each resulting chunk carries
    the filename and (where applicable) page number in its metadata.
    """
    logger.info(
        "ingest_file_request",
        filename=file.filename,
        content_type=file.content_type,
    )

    try:
        vector_store = VectorStore()
        processor = DocumentProcessor(vector_store)

        # Persist uploaded content to a temporary file, preserving suffix
        suffix = Path(file.filename or "upload").suffix or ".txt"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            result = await processor.process(
                source=tmp_path,
                filename=file.filename,
                metadata=None,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        REQUEST_COUNT.labels(endpoint="/ingest", status="success").inc()

        return IngestResponse(
            doc_ids=result["doc_ids"],
            chunks_created=result["chunks_created"],
            status=result["status"],
        )

    except IngestError:
        raise
    except Exception as exc:
        logger.error("ingest_file_failed", error=str(exc))
        REQUEST_COUNT.labels(endpoint="/ingest", status="error").inc()
        raise IngestError(f"Ingestion failed: {exc}") from exc
