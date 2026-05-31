"""Fetch evidence via Tavily / Perplexity and attach audit snapshot."""

from __future__ import annotations

from src.agents.state import AgentState
from src.config.settings import get_settings
from src.retrieval.service import (
    is_retrieval_available,
    mock_contexts_for_query,
    retrieve_contexts,
)


def retrieve_node(state: AgentState) -> dict:
    plan = state.get("verification_plan")
    processed = state.get("processed_query")
    query = state.get("query") or ""

    queries = []
    if plan and plan.retrieval_queries:
        queries = plan.retrieval_queries
    elif processed and processed.retrieval_queries:
        queries = processed.retrieval_queries
    elif query:
        queries = [query]

    settings = get_settings()
    snapshot: dict = {"queries": queries}

    if is_retrieval_available():
        contexts, snap = retrieve_contexts(queries)
        snapshot.update(snap)
        if not contexts and settings.use_mock_when_no_keys:
            contexts = mock_contexts_for_query(query, top_k=settings.retrieval_top_k)
            snapshot.update(
                {
                    "provider": "mock",
                    "result_count": len(contexts),
                    "fallback": "retrieval_failed_using_mock",
                    "warning": "Live retrieval returned no results — using mock sources",
                }
            )
    elif settings.use_mock_when_no_keys:
        contexts = mock_contexts_for_query(query, top_k=settings.retrieval_top_k)
        snapshot.update(
            {
                "provider": "mock",
                "result_count": len(contexts),
                "warning": "API keys missing — using mock sources for development",
            }
        )
    else:
        contexts = []
        snapshot.update(
            {
                "provider": "none",
                "error": "retrieval_not_configured",
                "result_count": 0,
            }
        )

    return {
        "contexts": contexts,
        "retrieval_snapshot": snapshot,
    }
