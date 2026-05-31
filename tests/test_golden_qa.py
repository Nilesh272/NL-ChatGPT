"""Golden Q&A set — measure unsupported claim rate (heuristic path, no API keys)."""

import json
from pathlib import Path

from src.models.schemas import ClaimVerdict, DraftAnswer, RetrievedContext
from src.verification.verifier import verify_draft

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "eval" / "golden_qa.jsonl"

MOCK_CONTEXTS = [
    RetrievedContext(
        id="src-1",
        url="https://example.com/one",
        title="Source One",
        snippet="Retrieval-augmented generation improves factual accuracy using external documents.",
        relevance_score=0.9,
    ),
    RetrievedContext(
        id="src-2",
        url="https://example.com/two",
        title="Source Two",
        snippet="LangGraph builds multi-step agent workflows with explicit state machines.",
        relevance_score=0.85,
    ),
]


def _load_golden():
    rows = []
    with open(GOLDEN_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def test_golden_set_has_ten_items():
    assert len(_load_golden()) == 10


def test_unsupported_rate_drops_after_refine_simulation():
    """Draft with planted false claim should have unsupported count >= 1."""
    rows = _load_golden()
    total_unsupported = 0
    for row in rows[:5]:
        draft = DraftAnswer(
            body=(
                f"Answer for {row['query']} [src-1]. "
                "The moon is made of cheese and has 50 moons [src-1]."
            ),
            inline_citations=[],
        )
        report = verify_draft(draft, MOCK_CONTEXTS, query=row["query"])
        total_unsupported += report.unsupported_critical_count
    assert total_unsupported >= 3
    cheese_claims = [
        c
        for row in rows[:1]
        for c in verify_draft(
            DraftAnswer(
                body="The moon is made of cheese [src-1].",
                inline_citations=[],
            ),
            MOCK_CONTEXTS,
        ).claims
        if "cheese" in c.text.lower()
    ]
    assert any(c.verdict == ClaimVerdict.UNSUPPORTED for c in cheese_claims)
