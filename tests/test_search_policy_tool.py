"""Tests for the US-023 read-only search_policy tool."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.policy_retriever import PolicyRetrieval
from app.services.policy_store import PolicySearchResult
from app.models.policy import PolicyChunk
from app.tools.search_policy import SearchPolicyTool


@dataclass
class FakeRetriever:
    retrievals: dict[str, PolicyRetrieval]
    searches: list[str] = field(default_factory=list)
    index_calls: int = 0

    def index_file(self, path: str | Path | None = None) -> list[PolicyChunk]:
        self.index_calls += 1
        return []

    def search(self, query: str) -> PolicyRetrieval:
        self.searches.append(query)
        return self.retrievals.get(query, PolicyRetrieval(query=query, chunks=[]))


def evidence(section_id: str, title: str, citation: str) -> PolicySearchResult:
    chunk = PolicyChunk(
        section_id=section_id,
        section_title=title,
        text=f"Evidence from {title}.",
        source_file="sample_policy.md",
        citation=citation,
    )
    return PolicySearchResult(chunk=chunk, relevance=0.8)


def test_supported_policy_queries_return_structured_evidence_and_citations() -> None:
    fake = FakeRetriever(
        retrievals={
            "water damage": PolicyRetrieval(
                query="water damage",
                chunks=[
                    evidence(
                        "section-1",
                        "Home Water Damage Coverage",
                        "sample_policy.md — Section 1: Home Water Damage Coverage",
                    )
                ],
            ),
            "personal property": PolicyRetrieval(
                query="personal property",
                chunks=[
                    evidence(
                        "section-2",
                        "Personal Property Protection",
                        "sample_policy.md — Section 2: Personal Property Protection",
                    )
                ],
            ),
        }
    )
    tool = SearchPolicyTool(retriever=fake)

    water = tool.run(query="water damage")
    personal = tool.run(query="personal property")

    assert water.status == "success"
    assert water.results[0].section_title == "Home Water Damage Coverage"
    assert water.results[0].citation.endswith("Section 1: Home Water Damage Coverage")
    assert personal.status == "success"
    assert personal.results[0].section_title == "Personal Property Protection"
    assert fake.index_calls == 1
    assert fake.searches == ["water damage", "personal property"]


def test_unsupported_query_returns_explicit_no_results() -> None:
    fake = FakeRetriever(retrievals={})
    tool = SearchPolicyTool(retriever=fake)

    result = tool.run(query="earthquake coverage")

    assert result.status == "not_found"
    assert result.results == []
    assert result.message == "No sufficiently relevant policy evidence was found."


def test_malformed_input_is_rejected_before_tool_execution() -> None:
    fake = FakeRetriever(retrievals={})
    tool = SearchPolicyTool(retriever=fake)

    with pytest.raises(ValueError):
        tool.run(query=" ")
    with pytest.raises(ValueError):
        tool.run(query="policy", path="/etc/passwd")
    assert fake.searches == []


def test_tool_is_read_only_and_agent_structured_call_has_same_output_shape() -> None:
    fake = FakeRetriever(
        retrievals={
            "water": PolicyRetrieval(
                query="water",
                chunks=[
                    evidence(
                        "section-1",
                        "Home Water Damage Coverage",
                        "sample_policy.md — Section 1: Home Water Damage Coverage",
                    )
                ],
            )
        }
    )
    tool = SearchPolicyTool(retriever=fake)

    structured_tool = tool.to_structured_tool()
    result = structured_tool.invoke({"query": "water"})

    assert result.status == "success"
    assert result.results[0].citation.startswith("sample_policy.md")
    assert fake.index_calls == 1
    assert not hasattr(fake, "write")
