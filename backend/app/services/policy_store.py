"""Chroma-backed local policy vector storage behind a small application interface."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

import chromadb
import numpy as np
from chromadb.api.types import EmbeddingFunction

from ..core.config import get_settings
from ..models.policy import PolicyChunk

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class VectorStoreError(Exception):
    """Controlled local vector-store failure."""


class PolicyVectorStore(Protocol):
    """Application-facing interface independent of Chroma details."""

    def build(self, chunks: Sequence[PolicyChunk]) -> None:
        ...

    def search(self, query: str, top_k: int) -> list["PolicySearchResult"]:
        ...

    def reset_or_rebuild(self, chunks: Sequence[PolicyChunk]) -> None:
        ...


@dataclass(frozen=True)
class PolicySearchResult:
    """Retrieved chunk plus a normalized cosine relevance score."""

    chunk: PolicyChunk
    relevance: float


class LocalHashEmbeddingFunction(EmbeddingFunction[list[str]]):
    """Deterministic offline embedding function for the small local policy corpus.

    This keeps Chroma usable without downloading a model or calling a provider. The
    vector-store abstraction remains replaceable for a later production embedding
    service, while tests stay deterministic and network-independent.
    """

    def __init__(self, dimension: int | None = None) -> None:
        settings = get_settings()
        self.dimension = dimension or settings.policy_embedding_dimension
        self.stopwords = frozenset(
            token.strip().lower()
            for token in settings.policy_embedding_stopwords.split(",")
            if token.strip()
        )

    @staticmethod
    def name() -> str:
        return "omnicare_local_hash"

    def get_config(self) -> dict[str, int]:
        return {"dimension": self.dimension}

    @staticmethod
    def build_from_config(config: dict[str, int]) -> "LocalHashEmbeddingFunction":
        return LocalHashEmbeddingFunction(dimension=int(config["dimension"]))

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> list[str]:
        return ["cosine"]

    def __call__(self, input: list[str]) -> list[np.ndarray]:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype=np.float32)
        tokens = [
            token
            for token in _TOKEN_PATTERN.findall(text.lower())
            if token not in self.stopwords
        ]
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dimension
            vector[index] += 1.0
        norm = np.linalg.norm(vector)
        if norm:
            vector /= norm
        return vector


class ChromaPolicyVectorStore:
    """Persistent local Chroma implementation of ``PolicyVectorStore``."""

    def __init__(
        self,
        index_path: str | Path | None = None,
        collection_name: str | None = None,
        embedding_function: LocalHashEmbeddingFunction | None = None,
    ) -> None:
        settings = get_settings()
        self._index_path = Path(index_path or settings.policy_index_path)
        self._collection_name = collection_name or settings.policy_collection_name
        self._embedding_function = embedding_function or LocalHashEmbeddingFunction()
        try:
            self._client = chromadb.PersistentClient(path=str(self._index_path))
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=self._embedding_function,
            )
        except Exception as exc:  # pragma: no cover - dependency-specific boundary
            raise VectorStoreError from exc

    def build(self, chunks: Sequence[PolicyChunk]) -> None:
        if not chunks:
            raise VectorStoreError("cannot index an empty policy")
        try:
            records = [chunk.model_dump(mode="json") for chunk in chunks]
            self._collection.upsert(
                ids=[record["section_id"] for record in records],
                documents=[record["text"] for record in records],
                metadatas=[
                    {
                        "section_id": record["section_id"],
                        "section_title": record["section_title"],
                        "source_file": record["source_file"],
                        "citation": record["citation"],
                    }
                    for record in records
                ],
            )
        except Exception as exc:  # pragma: no cover - dependency-specific boundary
            raise VectorStoreError from exc

    def search(self, query: str, top_k: int) -> list[PolicySearchResult]:
        normalized = query.strip()
        if not normalized or top_k <= 0:
            return []
        try:
            count = self._collection.count()
            if count == 0:
                return []
            result = self._collection.query(
                query_texts=[normalized],
                n_results=min(top_k, count),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:  # pragma: no cover - dependency-specific boundary
            raise VectorStoreError from exc

        documents = result.get("documents", [[]])[0] or []
        metadatas = result.get("metadatas", [[]])[0] or []
        distances = result.get("distances", [[]])[0] or []
        matches: list[PolicySearchResult] = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            if not isinstance(metadata, dict):
                continue
            try:
                chunk = PolicyChunk(
                    section_id=str(metadata["section_id"]),
                    section_title=str(metadata["section_title"]),
                    text=str(document),
                    source_file=str(metadata["source_file"]),
                    citation=str(metadata["citation"]),
                )
                relevance = max(0.0, min(1.0, 1.0 - float(distance)))
            except (KeyError, TypeError, ValueError):
                continue
            matches.append(PolicySearchResult(chunk=chunk, relevance=relevance))
        return matches

    def reset_or_rebuild(self, chunks: Sequence[PolicyChunk]) -> None:
        try:
            self._client.delete_collection(self._collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=self._embedding_function,
            )
        except Exception as exc:  # pragma: no cover - dependency-specific boundary
            raise VectorStoreError from exc
        self.build(chunks)
