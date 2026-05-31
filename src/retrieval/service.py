"""Unified retrieval with Tavily primary, Perplexity fallback, and session cache."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

from src.config.settings import get_settings
from src.models.schemas import RetrievedContext
from src.retrieval import perplexity as pplx
from src.retrieval import tavily as tav

_CACHE: dict[str, tuple[float, list[RetrievedContext], dict[str, Any]]] = {}


def _cache_key(queries: list[str], top_k: int) -> str:
    payload = json.dumps({"q": sorted(queries), "k": top_k}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _get_cached(key: str, ttl: int) -> Optional[tuple[list[RetrievedContext], dict[str, Any]]]:
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, contexts, snapshot = entry
    if time.time() - ts > ttl:
        del _CACHE[key]
        return None
    snapshot = {**snapshot, "cache_hit": True}
    return contexts, snapshot


def _set_cache(key: str, contexts: list[RetrievedContext], snapshot: dict[str, Any]) -> None:
    _CACHE[key] = (time.time(), contexts, snapshot)


def is_retrieval_available() -> bool:
    settings = get_settings()
    return bool(settings.tavily_api_key.strip() or settings.perplexity_api_key.strip())


def retrieve_contexts(
    queries: list[str],
    top_k: Optional[int] = None,
    use_cache: bool = True,
) -> tuple[list[RetrievedContext], dict[str, Any]]:
    """
    Fetch contexts from Tavily, falling back to Perplexity on failure.
    Returns (contexts, audit_snapshot).
    """
    settings = get_settings()
    k = top_k or settings.retrieval_top_k
    clean_queries = [q.strip() for q in queries if q and q.strip()]
    if not clean_queries:
        return [], {"provider": "none", "error": "no_queries", "result_count": 0}

    cache_key = _cache_key(clean_queries, k)
    if use_cache:
        cached = _get_cached(cache_key, settings.retrieval_cache_ttl_seconds)
        if cached:
            return cached

    errors: list[str] = []
    contexts: list[RetrievedContext] = []
    snapshot: dict[str, Any] = {"providers_tried": [], "queries": clean_queries}

    if settings.tavily_api_key.strip():
        try:
            contexts, snap = tav.search_tavily(clean_queries, top_k=k)
            snapshot["providers_tried"].append("tavily")
            snapshot.update(snap)
            if contexts:
                if use_cache:
                    _set_cache(cache_key, contexts, snapshot)
                return contexts, snapshot
            errors.append("tavily_returned_empty")
        except Exception as exc:
            errors.append(f"tavily_error:{exc}")

    if settings.perplexity_api_key.strip():
        try:
            contexts, snap = pplx.search_perplexity(clean_queries, top_k=k)
            snapshot["providers_tried"].append("perplexity")
            snapshot.update(snap)
            snapshot["fallback_used"] = True
            if contexts:
                if use_cache:
                    _set_cache(cache_key, contexts, snapshot)
                return contexts, snapshot
            errors.append("perplexity_returned_empty")
        except Exception as exc:
            errors.append(f"perplexity_error:{exc}")

    snapshot["errors"] = errors
    snapshot["result_count"] = 0
    return [], snapshot


def mock_contexts_for_query(query: str, top_k: int = 3) -> list[RetrievedContext]:
    """Deterministic mock sources when API keys are absent (dev/CI)."""
    from src.models.schemas import RetrievedContext

    base = [
        RetrievedContext(
            id="src-1",
            url="https://www.ibm.com/think/topics/retrieval-augmented-generation",
            title="What is RAG? | IBM",
            snippet=(
                "Retrieval-augmented generation (RAG) is an AI framework that pulls in "
                "facts from external sources to improve answer quality and reduce hallucinations."
            ),
            relevance_score=0.9,
        ),
        RetrievedContext(
            id="src-2",
            url="https://langchain-ai.github.io/langgraph/",
            title="LangGraph - LangChain",
            snippet=(
                "LangGraph is a library for building stateful, multi-actor applications with LLMs, "
                "including agentic workflows with cycles and persistence."
            ),
            relevance_score=0.88,
        ),
        RetrievedContext(
            id="src-3",
            url="https://docs.tavily.com/documentation/api-reference/endpoint/search",
            title="Tavily Search API",
            snippet=(
                "The Tavily Search API aggregates real-time web results optimized for LLM "
                "consumption and RAG pipelines."
            ),
            relevance_score=0.86,
        ),
    ]
    return base[:top_k]
