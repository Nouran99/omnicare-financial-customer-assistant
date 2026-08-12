"""Policy retrieval service over the local vector-store abstraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..core.config import get_settings
from ..models.policy import PolicyChunk
from .policy_loader import PolicyDocumentLoader
from .policy_store import PolicySearchResult, PolicyVectorStore

_WHITESPACE = re.compile(r"\s+")


class PolicyQueryError(Exception):
    """The policy query is malformed or exceeds the configured limit."""


@dataclass(frozen=True)
class PolicyRetrieval:
    """Typed retrieval result with an explicit evidence-found flag."""

    query: str
    chunks: list[PolicySearchResult]

    @property
    def found(self) -> bool:
        return bool(self.chunks)


class PolicyRetriever:
    """Normalize queries, apply thresholds, and preserve trusted chunk metadata."""

    def __init__(self, store: PolicyVectorStore) -> None:
        self._store = store
        self._settings = get_settings()

    def index_file(self, path: str | Path | None = None) -> list[PolicyChunk]:
        """Load and rebuild the local index from the configured policy file."""

        document_path = path or self._settings.policy_file_path
        chunks = PolicyDocumentLoader().load_file(document_path)
        self._store.reset_or_rebuild(chunks)
        return chunks

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        min_relevance: float | None = None,
    ) -> PolicyRetrieval:
        normalized = self._normalize_query(query)
        if not normalized:
            return PolicyRetrieval(query="", chunks=[])

        effective_top_k = top_k if top_k is not None else self._settings.policy_retrieval_top_k
        effective_threshold = (
            min_relevance
            if min_relevance is not None
            else self._settings.policy_retrieval_min_relevance
        )
        if effective_top_k <= 0:
            raise PolicyQueryError("top_k must be positive")
        if not 0 <= effective_threshold <= 1:
            raise PolicyQueryError("min_relevance must be between 0 and 1")

        matches = self._store.search(normalized, effective_top_k)
        accepted = [
            match for match in matches if match.relevance >= effective_threshold
        ]
        return PolicyRetrieval(query=normalized, chunks=accepted)

    @staticmethod
    def _normalize_query(query: str) -> str:
        if not isinstance(query, str):
            raise PolicyQueryError("query must be text")
        normalized = _WHITESPACE.sub(" ", query).strip()
        if len(normalized) > get_settings().policy_query_max_length:
            raise PolicyQueryError("query exceeds the configured length")
        return normalized
