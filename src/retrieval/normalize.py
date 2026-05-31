"""Normalize and deduplicate raw search API results."""

from __future__ import annotations

import re
from typing import Any, Iterable, Optional
from urllib.parse import urlparse

from src.models.schemas import RetrievedContext

_SNIPPET_MAX = 500


def _canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or ""
    return f"{netloc}{path}"


def _trim_snippet(text: str, max_len: int = _SNIPPET_MAX) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3].rstrip() + "..."


def assign_sequential_ids(
    contexts: list[RetrievedContext],
    prefix: str = "src",
) -> list[RetrievedContext]:
    """Renumber source IDs after merge/dedupe so [src-N] citations are unambiguous."""
    renumbered: list[RetrievedContext] = []
    for i, ctx in enumerate(contexts):
        renumbered.append(
            RetrievedContext(
                id=f"{prefix}-{i + 1}",
                url=ctx.url,
                title=ctx.title,
                snippet=ctx.snippet,
                published_at=ctx.published_at,
                relevance_score=ctx.relevance_score,
            )
        )
    return renumbered


def dedupe_contexts(contexts: Iterable[RetrievedContext]) -> list[RetrievedContext]:
    """Remove duplicate URLs, keeping the highest relevance score."""
    by_url: dict[str, RetrievedContext] = {}
    for ctx in contexts:
        key = _canonical_url(ctx.url)
        if not key:
            continue
        existing = by_url.get(key)
        if existing is None or ctx.relevance_score > existing.relevance_score:
            by_url[key] = ctx
    return sorted(by_url.values(), key=lambda c: c.relevance_score, reverse=True)


def normalize_tavily_result(
    item: dict[str, Any],
    index: int,
    relevance_score: Optional[float] = None,
) -> Optional[RetrievedContext]:
    url = (item.get("url") or "").strip()
    if not url:
        return None
    title = (item.get("title") or "Untitled").strip()
    snippet = _trim_snippet(item.get("content") or item.get("snippet") or "")
    if not snippet:
        return None
    score = relevance_score
    if score is None:
        raw = item.get("score")
        score = float(raw) if raw is not None else max(0.5, 1.0 - (index * 0.05))
    return RetrievedContext(
        id=f"src-{index + 1}",
        url=url,
        title=title,
        snippet=snippet,
        published_at=item.get("published_date"),
        relevance_score=min(max(float(score), 0.0), 1.0),
    )


def normalize_tavily_response(
    response: dict[str, Any],
    min_relevance: float = 0.0,
    top_k: int = 6,
) -> list[RetrievedContext]:
    """Convert Tavily search response to RetrievedContext list."""
    results = response.get("results") or []
    contexts: list[RetrievedContext] = []
    for i, item in enumerate(results):
        ctx = normalize_tavily_result(item, index=i)
        if ctx and ctx.relevance_score >= min_relevance:
            contexts.append(ctx)
    return dedupe_contexts(contexts)[:top_k]


def normalize_perplexity_result(
    item: dict[str, Any],
    index: int,
) -> Optional[RetrievedContext]:
    url = (item.get("url") or item.get("link") or "").strip()
    if not url:
        return None
    title = (item.get("title") or item.get("name") or "Untitled").strip()
    snippet = _trim_snippet(item.get("snippet") or item.get("content") or item.get("text") or "")
    if not snippet:
        return None
    return RetrievedContext(
        id=f"pplx-{index + 1}",
        url=url,
        title=title,
        snippet=snippet,
        relevance_score=max(0.5, 1.0 - (index * 0.06)),
    )
