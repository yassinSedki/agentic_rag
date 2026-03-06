"""Vector store package.

Concrete backends live in this package (e.g. ``chroma.py``), and the
high-level :class:`VectorStore` façade is defined in
``vector_store.py``.

Application code should import and use ``VectorStore`` rather than
referencing a specific backend directly.
"""

from app.vectorstore.vector_store import VectorStore  # re-export convenience

__all__ = ["VectorStore"]

