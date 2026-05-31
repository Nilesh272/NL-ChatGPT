from src.models.schemas import RetrievedContext
from src.retrieval.normalize import assign_sequential_ids, dedupe_contexts, normalize_tavily_response


def test_normalize_tavily_response_dedupes_and_limits():
    response = {
        "results": [
            {
                "url": "https://example.com/a",
                "title": "A",
                "content": "First snippet about RAG.",
                "score": 0.95,
            },
            {
                "url": "https://example.com/a",
                "title": "A duplicate",
                "content": "Duplicate URL should merge.",
                "score": 0.5,
            },
            {
                "url": "https://example.com/b",
                "title": "B",
                "content": "Second snippet.",
                "score": 0.8,
            },
        ]
    }
    contexts = normalize_tavily_response(response, top_k=2)
    assert len(contexts) == 2
    assert contexts[0].relevance_score >= contexts[1].relevance_score
    assert contexts[0].url == "https://example.com/a"


def test_dedupe_keeps_highest_score():
    a = RetrievedContext(
        id="src-1",
        url="https://x.com/page",
        title="Low",
        snippet="s",
        relevance_score=0.5,
    )
    b = RetrievedContext(
        id="src-2",
        url="https://www.x.com/page/",
        title="High",
        snippet="s2",
        relevance_score=0.9,
    )
    out = dedupe_contexts([a, b])
    assert len(out) == 1
    assert out[0].relevance_score == 0.9


def test_assign_sequential_ids_after_merge():
    contexts = [
        RetrievedContext(
            id="src-1",
            url="https://a.com",
            title="A",
            snippet="a",
            relevance_score=0.9,
        ),
        RetrievedContext(
            id="src-1",
            url="https://b.com",
            title="B",
            snippet="b",
            relevance_score=0.8,
        ),
    ]
    out = assign_sequential_ids(contexts)
    assert [c.id for c in out] == ["src-1", "src-2"]
