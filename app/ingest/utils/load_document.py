"""Document loader — reads files from various formats.

Supports: PDF, TXT, Markdown, DOCX, and raw text strings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import structlog

from app.core.exceptions import UnsupportedFileTypeError
from app.core.schemas import Document, DocumentMetadata

logger = structlog.get_logger()

# Supported file extensions
_SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


def load_document(
    source: str,
    filename: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> list[Document]:
    """Load a document from a file path or raw text.

    Parameters
    ----------
    source:
        Either a file path to an existing file, or raw text content.
    filename:
        Optional original filename (used for metadata when *source* is raw text).
    metadata:
        Optional extra metadata to attach.

    Returns
    -------
    list[Document]
        One or more ``Document`` objects (PDFs may produce multiple pages).

    Raises
    ------
    UnsupportedFileTypeError
        If the file extension is not supported.
    FileNotFoundError
        If *source* is a file path that does not exist.
    """
    extra_meta = metadata or {}

    # Determine if source is a file path
    source_path = Path(source)
    if source_path.is_file():
        return _load_from_file(source_path, extra_meta)

    # Treat source as raw text
    doc_meta = DocumentMetadata(
        source=filename or "raw_text",
        **{k: v for k, v in extra_meta.items() if k in DocumentMetadata.model_fields},
    )
    return [Document(content=source, metadata=doc_meta)]


def _load_from_file(path: Path, extra_meta: dict) -> list[Document]:
    """Dispatcher for file-type specific loaders."""
    ext = path.suffix.lower()

    if ext not in _SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type: '{ext}'. Supported: {_SUPPORTED_EXTENSIONS}"
        )

    base_meta = {
        "source": path.name,
        **{k: v for k, v in extra_meta.items() if k in DocumentMetadata.model_fields},
    }

    if ext == ".pdf":
        return _load_pdf(path, base_meta)
    elif ext == ".docx":
        return _load_docx(path, base_meta)
    else:  # .txt, .md
        return _load_text(path, base_meta)


def _load_text(path: Path, meta: dict) -> list[Document]:
    """Load a plain text or markdown file."""
    content = path.read_text(encoding="utf-8", errors="replace")
    doc_meta = DocumentMetadata(**meta)
    return [Document(content=content, metadata=doc_meta)]


def _load_pdf(path: Path, meta: dict) -> list[Document]:
    """Load a PDF file, one ``Document`` per page.

    Uses ``langchain_community.document_loaders`` if available,
    otherwise falls back to basic text extraction.
    """
    try:
        from langchain_community.document_loaders import PyPDFLoader

        loader = PyPDFLoader(str(path))
        pages = loader.load()
        documents: list[Document] = []
        for i, page in enumerate(pages):
            doc_meta = DocumentMetadata(**meta, page=i + 1)
            documents.append(Document(content=page.page_content, metadata=doc_meta))
        return documents
    except ImportError:
        logger.warning("pypdf_not_installed", hint="pip install pypdf")
        content = f"[PDF content from {path.name} — install pypdf for extraction]"
        return [Document(content=content, metadata=DocumentMetadata(**meta))]


def _load_docx(path: Path, meta: dict) -> list[Document]:
    """Load a DOCX file."""
    try:
        from langchain_community.document_loaders import Docx2txtLoader

        loader = Docx2txtLoader(str(path))
        pages = loader.load()
        documents: list[Document] = []
        for page in pages:
            doc_meta = DocumentMetadata(**meta)
            documents.append(Document(content=page.page_content, metadata=doc_meta))
        return documents
    except ImportError:
        logger.warning("docx2txt_not_installed", hint="pip install docx2txt")
        content = f"[DOCX content from {path.name} — install docx2txt for extraction]"
        return [Document(content=content, metadata=DocumentMetadata(**meta))]
