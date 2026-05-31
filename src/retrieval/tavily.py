"""Tavily web search — primary retrieval for Phase 1."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, List, Optional, Tuple

from src.config.settings import get_settings
from src.models.schemas import RetrievedContext
from src.retrieval.normalize import assign_sequential_ids, dedupe_contexts, normalize_tavily_response


def _search_single_query(client: Any, query: str, top_k: int) -> Tuple[str, dict]:
    """Run one Tavily search; returns (query, response dict)."""
    response = client.search(
        query=query,
        max_results=top_k,
        search_depth="advanced",
        include_answer=False,
        include_raw_content=False,
    )
    if hasattr(response, "model_dump"):
        response = response.model_dump()
    elif not isinstance(response, dict):
        response = dict(response) if response else {}
    return query, response


def search_tavily(
    queries: List[str],
    top_k: Optional[int] = None,
    api_key: Optional[str] = None,
) -> Tuple[List[RetrievedContext], dict]:
    """
    Run Tavily search for one or more queries.
    Returns normalized contexts and a raw audit snapshot.
    """
    settings = get_settings()
    key = (api_key or settings.tavily_api_key).strip()
    if not key:
        raise ValueError("TAVILY_API_KEY is not configured.")

    try:
        from tavily import TavilyClient
    except ImportError as exc:
        raise ImportError("Install tavily-python: pip install tavily-python") from exc

    k = top_k or settings.retrieval_top_k
    client = TavilyClient(api_key=key)
    all_contexts: List[RetrievedContext] = []
    raw_queries: List[dict] = []
    clean = [q.strip() for q in queries if q and q.strip()]

    if len(clean) <= 1:
        for q in clean:
            _, response = _search_single_query(client, q, k)
            raw_queries.append({"query": q, "response": response})
            all_contexts.extend(normalize_tavily_response(response, top_k=k))
    else:
        max_workers = min(len(clean), 4)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_search_single_query, client, q, k): q for q in clean
            }
            for future in as_completed(futures):
                q, response = future.result()
                raw_queries.append({"query": q, "response": response})
                all_contexts.extend(normalize_tavily_response(response, top_k=k))

    contexts = assign_sequential_ids(dedupe_contexts(all_contexts)[:k])
    snapshot = {
        "provider": "tavily",
        "queries": raw_queries,
        "result_count": len(contexts),
        "parallel_queries": len(clean) > 1,
    }
    return contexts, snapshot
