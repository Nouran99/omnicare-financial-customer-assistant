"""CrewAI-compatible read-only policy retrieval tool for US-023."""

from __future__ import annotations

from typing import Any

from crewai.tools import BaseTool
from pydantic import BaseModel, PrivateAttr

from ..core.config import Settings, get_settings
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
    _last_output: SearchPolicyOutput | None = PrivateAttr(default=None)
    _last_query: str | None = PrivateAttr(default=None)
    _settings: Settings = PrivateAttr()

    def __init__(
        self,
        *,
        retriever: PolicyRetriever | None = None,
        settings: Settings | None = None,
        **data: Any,
    ) -> None:
        super().__init__(**data)
        self._retriever = retriever
        self._settings = settings or get_settings()

    @property
    def last_query(self) -> str | None:
        """Return the latest submitted policy query for safe summary construction."""

        return self._last_query

    @property
    def last_output(self) -> SearchPolicyOutput | None:
        """Return the latest sanitized policy result for Flow composition."""

        return self._last_output

    def reset_observation(self) -> None:
        """Clear the latest result before a new Flow request."""

        self._last_output = None
        self._last_query = None

    def _run(self, query: str) -> SearchPolicyOutput:
        self._last_query = query
        try:
            retriever = self._get_retriever()
            retrieval = retriever.search(query)
        except (PolicyQueryError, PolicyDocumentError, VectorStoreError):
            output = SearchPolicyOutput(
                status="failure",
                message="Policy retrieval is temporarily unavailable.",
            )
            self._last_output = output
            return output
        except Exception:  # pragma: no cover - defensive tool boundary
            output = SearchPolicyOutput(
                status="failure",
                message="Policy retrieval failed safely.",
            )
            self._last_output = output
            return output

        if not retrieval.found:
            output = SearchPolicyOutput(
                status="not_found",
                message="No sufficiently relevant policy evidence was found.",
            )
            self._last_output = output
            return output

        output = SearchPolicyOutput(
            status="success",
            results=[
                self._evidence_from_chunk(result.chunk)
                for result in retrieval.chunks
            ],
        )
        self._last_output = output
        return output

    def _get_retriever(self) -> PolicyRetriever:
        if self._retriever is None:
            self._retriever = PolicyRetriever(
                ChromaPolicyVectorStore(settings=self._settings),
                settings=self._settings,
            )
        if not self._indexed:
            self._retriever.index_file()
            self._indexed = True
        return self._retriever

    def evidence_context(self) -> str:
        """Return bounded trusted evidence for the agent task context."""

        output = self._last_output
        if output is None or output.status != "success":
            return "No sufficiently relevant policy evidence was found."
        return "\n".join(
            f"{result.citation}: {result.text}"
            for result in output.results
        )

    @staticmethod
    def _evidence_from_chunk(chunk: PolicyChunk) -> PolicyEvidenceOutput:
        return PolicyEvidenceOutput(
            section_title=chunk.section_title,
            text=chunk.text,
            citation=chunk.citation,
        )
