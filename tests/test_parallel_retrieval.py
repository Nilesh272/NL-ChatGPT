"""Phase 6: parallel Tavily query execution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.retrieval import tavily as tav


def _fake_response(query: str) -> dict:
    return {
        "results": [
            {
                "url": f"https://example.com/{query.replace(' ', '-')}",
                "title": query,
                "content": f"Snippet for {query}",
                "score": 0.9,
            }
        ]
    }


@patch("tavily.TavilyClient")
def test_parallel_tavily_multiple_queries(mock_client_cls):
    client = MagicMock()
    mock_client_cls.return_value = client
    client.search.side_effect = lambda query, **kwargs: _fake_response(query)

    with patch("src.retrieval.tavily.get_settings") as mock_settings:
        mock_settings.return_value.tavily_api_key = "tvly-test"
        mock_settings.return_value.retrieval_top_k = 6

        contexts, snap = tav.search_tavily(
            ["query one", "query two", "query three"],
            top_k=6,
            api_key="tvly-test",
        )

    assert snap.get("parallel_queries") is True
    assert snap["result_count"] >= 1
    assert len(snap["queries"]) == 3
    assert client.search.call_count == 3


@patch("tavily.TavilyClient")
def test_single_query_not_marked_parallel(mock_client_cls):
    client = MagicMock()
    mock_client_cls.return_value = client
    client.search.return_value = _fake_response("only")

    with patch("src.retrieval.tavily.get_settings") as mock_settings:
        mock_settings.return_value.tavily_api_key = "tvly-test"
        mock_settings.return_value.retrieval_top_k = 3

        _, snap = tav.search_tavily(["only one query"], api_key="tvly-test")

    assert snap.get("parallel_queries") is False
