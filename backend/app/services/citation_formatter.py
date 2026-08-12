"""Derive public citations only from trusted policy chunk metadata."""

from __future__ import annotations

from collections.abc import Iterable

from ..models.policy import PolicyChunk


def format_citations(chunks: Iterable[PolicyChunk]) -> list[str]:
    """Return stable, deduplicated citation strings in retrieval order."""

    citations: list[str] = []
    for chunk in chunks:
        citation = chunk.citation.strip()
        if citation and citation not in citations:
            citations.append(citation)
    return citations
