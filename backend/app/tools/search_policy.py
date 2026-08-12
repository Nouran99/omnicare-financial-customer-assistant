"""CrewAI-compatible read-only policy retrieval tool for US-023."""

from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, PrivateAttr

from ..models.policy import PolicyChunk
from ..services.policy_loader import PolicyDocumentError
from ..services.policy_retriever import PolicyQueryError, PolicyRetriever
from ..services.policy_store import ChromaPolicyVectorStore, VectorStoreError
from .schemas import (
    PolicyEvidenceOutput,
    SearchPolicyInput,
    SearchPolicyOutput,
)


class SearchPolicyTool(BaseTool):
    """Retrieve trusted policy evidence without exposing files or index internals."""

    name: str = "search_policy"
    description: str = (
        "Search the supplied local policy for relevant coverage evidence and citations. "
        "Use for policy questions; returns structured evidence or a safe no-results outcome."
    )
    args_schema: type[BaseModel] = SearchPolicyInput
    result_schema: type[BaseModel] = SearchPolicyOutput

    _retriever: PolicyRetriever | None = PrivateAttr(default=None)
    _indexed: bool = PrivateAttr(default=False)

    def __init__(
        self,
        *,
        retriever: PolicyRetriever | None = None,
        **data: Any,
    ) -> None:
        super().__init__(**data)
        self._retriever = retriever

    def _run(self, query: str) -> SearchPolicyOutput:
        try:
            retriever = self._get_retriever()
            retrieval = retriever.search(query)
        except (PolicyQueryError, PolicyDocumentError, VectorStoreError):
            return SearchPolicyOutput(
                status="failure",
                message="Policy retrieval is temporarily unavailable.",
            )
        except Exception:  # pragma: no cover - defensive tool boundary
            return SearchPolicyOutput(
                status="failure",
                message="Policy retrieval failed safely.",
            )

        if not retrieval.found:
            return SearchPolicyOutput(
                status="not_found",
                message="No sufficiently relevant policy evidence was found.",
            )

        return SearchPolicyOutput(
            status="success",
            results=[
                self._evidence_from_chunk(result.chunk)
                for result in retrieval.chunks
            ],
        )

    def _get_retriever(self) -> PolicyRetriever:
        if self._retriever is None:
            self._retriever = PolicyRetriever(ChromaPolicyVectorStore())
        if not self._indexed:
            self._retriever.index_file()
            self._indexed = True
        return self._retriever

    @staticmethod
    def _evidence_from_chunk(chunk: PolicyChunk) -> PolicyEvidenceOutput:
        return PolicyEvidenceOutput(
            section_title=chunk.section_title,
            text=chunk.text,
            citation=chunk.citation,
        )
