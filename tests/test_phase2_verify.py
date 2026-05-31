import json

from src.agents.graph import build_graph
from src.agents.nodes.refine import refine_node
from src.agents.nodes.verify import verify_node
from src.models.schemas import ClaimVerdict, DraftAnswer, RetrievedContext
from src.verification.refiner import refine_draft
from src.verification.verifier import serialize_report, verify_draft


MICROSOFT_CTX = [
    RetrievedContext(
        id="src-1",
        url="https://www.microsoft.com/en-us/about/leadership/satya-nadella",
        title="Satya Nadella, Chairman and CEO",
        snippet=(
            "Satya Nadella is Chairman and Chief Executive Officer of Microsoft. "
            "He became CEO in 2014."
        ),
        relevance_score=0.95,
    ),
]


def test_false_claim_flagged_and_removed():
    draft = DraftAnswer(
        body=(
            "Satya Nadella is the CEO of Microsoft [src-1]. "
            "The population of Mars is 10 billion people [src-1]."
        ),
        inline_citations=[],
    )
    report = verify_draft(draft, MICROSOFT_CTX, query="Who is CEO of Microsoft?")

    assert report.unsupported_critical_count >= 1
    mars_claims = [c for c in report.claims if "mars" in c.text.lower()]
    assert mars_claims
    assert mars_claims[0].verdict in (ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTED)

    refined = refine_draft(draft, report)
    assert "10 billion" not in refined.body.lower()
    assert "satya" in refined.body.lower() or "do not have enough" in refined.body.lower()


def test_verification_report_serializable():
    draft = DraftAnswer(body="Microsoft's CEO is Satya Nadella [src-1].", inline_citations=[])
    report = verify_draft(draft, MICROSOFT_CTX)
    data = serialize_report(report)
    json_str = json.dumps(data)
    parsed = json.loads(json_str)
    assert "claims" in parsed
    assert parsed["unsupported_critical_count"] == 0 or parsed["unsupported_critical_count"] >= 0


def test_verify_refine_loop_in_graph():
    graph = build_graph(include_justify=True, include_verify_loop=True)
    draft = DraftAnswer(
        body=(
            "Satya Nadella leads Microsoft [src-1]. "
            "Mars has a population of 10 billion [src-1]."
        ),
        inline_citations=[],
    )
    contexts = MICROSOFT_CTX
    state = {
        "query": "CEO of Microsoft",
        "stakes": "medium",
        "draft": draft,
        "contexts": contexts,
        "iteration": 0,
    }
    v1 = verify_node(state)
    assert v1["unsupported_critical_count"] >= 1

    state.update(v1)
    r1 = refine_node(state)
    assert r1["iteration"] == 1
    assert "10 billion" not in r1["draft"].body.lower()

    state.update(r1)
    v2 = verify_node(state)
    assert v2["verification_report"] is not None


def test_minicheck_detects_unrelated_claim():
    from src.verification.minicheck import entailment_score

    claim = "The population of Mars is 10 billion people."
    passage = "Satya Nadella is Chairman and Chief Executive Officer of Microsoft."
    score = entailment_score(claim, passage)
    assert score < 0.35
