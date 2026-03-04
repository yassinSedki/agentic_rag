"""Text cleaning utilities for ingested documents.

Normalises whitespace, strips boilerplate patterns, and drops
empty pages / chunks before chunking.
"""

from __future__ import annotations

import re

from app.core.schemas import Document


def clean_documents(documents: list[Document]) -> list[Document]:
    """Clean a list of documents, returning only non-empty results.

    Operations performed:
    1. Normalise whitespace (collapse runs, strip edges).
    2. Remove common boilerplate headers / footers.
    3. Drop pages that are empty after cleaning.
    """
    cleaned: list[Document] = []
    for doc in documents:
        text = _normalize_whitespace(doc.content)
        text = _strip_boilerplate(text)
        if text and len(text.strip()) > 10:
            cleaned.append(doc.model_copy(update={"content": text}))
    return cleaned


def _normalize_whitespace(text: str) -> str:
    """Collapse multiple whitespace chars into a single space; trim edges."""
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_boilerplate(text: str) -> str:
    """Remove common boilerplate patterns from extracted text."""
    # Page numbers like "Page 1 of 10", "- 3 -"
    text = re.sub(r"(?i)page\s+\d+\s+(of\s+\d+)?", "", text)
    text = re.sub(r"-\s*\d+\s*-", "", text)

    # Common footer patterns
    text = re.sub(r"(?i)confidential\s*[–—-]\s*do not distribute", "", text)
    text = re.sub(r"(?i)all rights reserved\.?", "", text)

    return text.strip()
