from src.agents.graph import run_graph
from src.models.schemas import ConfidenceBand, JustificationBundle


def test_run_graph_returns_justification_bundle():
    bundle = run_graph("What is Agentic RAG?", stakes="medium")
    assert isinstance(bundle, JustificationBundle)
    assert bundle.phase in ("0-stub", "1-rag", "2-verified", "3-ui", "5-judgment")
    assert len(bundle.claims) >= 1
    assert len(bundle.citations) >= 1
    assert bundle.overall_confidence in ConfidenceBand


def test_answer_mentions_query():
    bundle = run_graph("What is Agentic RAG?")
    assert "Agentic RAG" in bundle.answer or "agentic" in bundle.answer.lower()
