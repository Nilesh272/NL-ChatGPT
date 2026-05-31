from unittest.mock import patch

from src.agents.graph import run_graph
from src.agents.nodes.draft import INSUFFICIENT_MSG, draft_node
from src.models.schemas import JustificationBundle


def test_phase1_mock_pipeline_has_three_citations():
    bundle = run_graph("What is Agentic RAG?", stakes="medium")
    assert isinstance(bundle, JustificationBundle)
    assert bundle.phase in ("1-rag", "2-verified", "3-ui", "5-judgment")
    assert len(bundle.citations) >= 3
    for cite in bundle.citations:
        assert cite.url.startswith("http")


def test_empty_retrieval_refuses_to_guess():
    state = {
        "query": "Who is the CEO of UnknownCorp?",
        "stakes": "high",
        "contexts": [],
    }
    result = draft_node(state)
    draft = result["draft"]
    assert INSUFFICIENT_MSG.split(".")[0] in draft.body


@patch("src.agents.nodes.retrieve.retrieve_contexts")
def test_tavily_contexts_used_in_pipeline(mock_retrieve):
    from src.models.schemas import RetrievedContext

    mock_retrieve.return_value = (
        [
            RetrievedContext(
                id="src-1",
                url="https://openai.com/about",
                title="About",
                snippet="OpenAI information.",
                relevance_score=0.9,
            ),
            RetrievedContext(
                id="src-2",
                url="https://www.anthropic.com/company",
                title="Anthropic",
                snippet="Anthropic information.",
                relevance_score=0.85,
            ),
            RetrievedContext(
                id="src-3",
                url="https://ai.google/",
                title="Google AI",
                snippet="Google AI information.",
                relevance_score=0.8,
            ),
        ],
        {"provider": "tavily", "result_count": 3},
    )

    with patch("src.agents.nodes.retrieve.is_retrieval_available", return_value=True):
        bundle = run_graph("What is Agentic RAG?")
    assert len(bundle.citations) >= 3
    urls = {c.url for c in bundle.citations}
    assert "https://openai.com/about" in urls
