"""US-016 through US-020 tests without a live provider or network dependency."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.policy import PolicyChunk
from app.services.citation_formatter import format_citations
from app.services.policy_loader import (
    PolicyDocumentLoader,
    PolicyDocumentMalformedError,
)
from app.services.policy_retriever import PolicyQueryError, PolicyRetriever
from app.services.policy_store import ChromaPolicyVectorStore, VectorStoreError


POLICY_PATH = Path(__file__).parents[1] / "data" / "sample_policy.md"


def load_chunks() -> list[PolicyChunk]:
    return PolicyDocumentLoader().load_file(POLICY_PATH)


def make_store(tmp_path: Path) -> ChromaPolicyVectorStore:
    return ChromaPolicyVectorStore(
        index_path=tmp_path / "chroma",
        collection_name="policy_test_collection",
    )


def test_policy_loader_creates_stable_section_chunks() -> None:
    chunks = load_chunks()

    assert len(chunks) == 2
    assert [chunk.section_id for chunk in chunks] == ["section-1", "section-2"]
    assert chunks[0].section_title == "Home Water Damage Coverage"
    assert chunks[1].section_title == "Personal Property Protection"
    assert chunks[0].citation == (
        "sample_policy.md — Section 1: Home Water Damage Coverage"
    )
    assert "$25,000" in chunks[0].text
    assert "$10,000" in chunks[1].text


@pytest.mark.parametrize("content", ["", "# Title only", "## Section 1: Missing body\n"])
def test_policy_loader_rejects_empty_or_malformed_documents(content: str) -> None:
    with pytest.raises(PolicyDocumentMalformedError):
        PolicyDocumentLoader().load_text(content)


def test_chroma_store_indexes_and_searches_without_network(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    chunks = load_chunks()

    assert store.search("water damage", top_k=2) == []
    store.build(chunks)
    matches = store.search("sudden pipe burst water damage", top_k=2)

    assert matches
    assert matches[0].chunk.section_id == "section-1"
    assert matches[0].chunk.citation.endswith("Section 1: Home Water Damage Coverage")
    assert 0 <= matches[0].relevance <= 1


def test_chroma_build_is_idempotent_and_rebuild_is_clean(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    chunks = load_chunks()

    store.build(chunks)
    store.build(chunks)
    personal_property = store.search("electronics furniture jewelry", top_k=3)
    assert len(personal_property) == 2

    store.reset_or_rebuild(chunks[:1])
    rebuilt_matches = store.search("personal property electronics", top_k=3)
    assert rebuilt_matches
    assert all(match.chunk.section_id == "section-1" for match in rebuilt_matches)
    assert store.search("pipe bursts", top_k=3)


def test_empty_index_search_and_empty_build_behavior(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    assert store.search("anything", top_k=2) == []
    with pytest.raises(VectorStoreError):
        store.build([])


def test_policy_retriever_applies_threshold_and_preserves_metadata(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    retriever = PolicyRetriever(store)
    retriever.index_file(POLICY_PATH)

    water = retriever.search("  Is sudden pipe-burst water damage covered?  ")
    property_result = retriever.search("How much electronics coverage is available?")
    unsupported = retriever.search("Does the policy cover earthquake damage?")

    assert water.found is True
    assert water.query == "Is sudden pipe-burst water damage covered?"
    assert water.chunks[0].chunk.section_id == "section-1"
    assert property_result.chunks[0].chunk.section_id == "section-2"
    assert unsupported.found is False
    assert unsupported.chunks == []


def test_policy_retriever_rejects_invalid_query_controls(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    retriever = PolicyRetriever(store)

    with pytest.raises(PolicyQueryError):
        retriever.search("x", top_k=0)
    with pytest.raises(PolicyQueryError):
        retriever.search("x", min_relevance=1.1)


def test_citation_formatter_deduplicates_in_retrieval_order() -> None:
    chunks = load_chunks()
    reordered = [chunks[1], chunks[0], chunks[1]]

    assert format_citations(reordered) == [chunks[1].citation, chunks[0].citation]
    assert format_citations([]) == []
