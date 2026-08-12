"""Tests proving the supplied policy fixture contains only required facts."""

from pathlib import Path


POLICY_PATH = Path(__file__).parents[1] / "data" / "sample_policy.md"


def test_sample_policy_contains_required_sections_and_facts() -> None:
    policy = POLICY_PATH.read_text(encoding="utf-8").lower()

    required_phrases = [
        "# omnicare sample policy",
        "## section 1: home water damage coverage",
        "sudden pipe bursts",
        "$25,000",
        "$500",
        "gradual leaks",
        "flood damage",
        "## section 2: personal property protection",
        "$10,000",
        "$2,500",
        "individual appraisal receipts",
    ]

    assert all(phrase in policy for phrase in required_phrases)
    assert "earthquake" not in policy.lower()
    assert "claim deadline" not in policy.lower()
