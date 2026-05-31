"""Perplexity API fallback when Tavily is unavailable."""

from __future__ import annotations

from typing import Any

import httpx

from src.config.settings import get_settings
from src.models.schemas import RetrievedContext
from src.retrieval.normalize import dedupe_contexts, normalize_perplexity_result


def search_perplexity(
    queries: list[str],
    top_k: int | None = None,
    api_key: str | None = None,
) -> tuple[list[RetrievedContext], dict[str, Any]]:
    """Search via Perplexity chat completions API (sonar) with web citations."""
    settings = get_settings()
    key = (api_key or settings.perplexity_api_key).strip()
    if not key:
        raise ValueError("PERPLEXITY_API_KEY is not configured.")

    k = top_k or settings.retrieval_top_k
    query = " ".join(q.strip() for q in queries if q.strip())[:2000]
    if not query:
        return [], {"provider": "perplexity", "queries": [], "result_count": 0}

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer using web search. Return factual snippets only; "
                    "do not invent URLs."
                ),
            },
            {"role": "user", "content": query},
        ],
        "temperature": 0.1,
    }

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    citations = data.get("citations") or []
    contexts: list[RetrievedContext] = []
    for i, url in enumerate(citations):
        if isinstance(url, str) and url.startswith("http"):
            ctx = normalize_perplexity_result(
                {"url": url, "title": f"Source {i + 1}", "snippet": ""},
                index=i,
            )
            if ctx:
                contexts.append(ctx)

    # Enrich snippets from search_results if present
    search_results = data.get("search_results") or []
    for i, item in enumerate(search_results):
        if isinstance(item, dict):
            ctx = normalize_perplexity_result(item, index=i)
            if ctx:
                contexts.append(ctx)

    message = (data.get("choices") or [{}])[0].get("message") or {}
    content = (message.get("content") or "").strip()
    if content and contexts:
        contexts[0] = contexts[0].model_copy(
            update={"snippet": (contexts[0].snippet or content[:400])}
        )

    contexts = dedupe_contexts(contexts)[:k]
    snapshot = {
        "provider": "perplexity",
        "queries": [{"query": query}],
        "result_count": len(contexts),
        "has_content": bool(content),
    }
    return contexts, snapshot
