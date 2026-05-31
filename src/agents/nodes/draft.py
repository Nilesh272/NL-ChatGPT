"""Grounded draft generation with mandatory source citations."""

from __future__ import annotations

import re
from typing import List, Set

from pydantic import BaseModel, Field

from src.agents.state import AgentState
from src.llm.client import get_chat_model, is_llm_available
from src.models.schemas import Citation, DraftAnswer, RetrievedContext
from src.prompts.templates import MASTER_SYSTEM_PROMPT


class DraftLLMOutput(BaseModel):
    body: str = Field(description="Answer with inline [src-N] citation markers")
    cited_source_ids: List[str] = Field(
        default_factory=list,
        description="Source IDs referenced in the answer",
    )


INSUFFICIENT_MSG = (
    "I do not have enough information to answer this accurately. "
    "No relevant sources were retrieved. Please refine your question or try again later."
)


def _format_sources_block(contexts: List[RetrievedContext]) -> str:
    lines = []
    for ctx in contexts:
        lines.append(
            f"[{ctx.id}] {ctx.title}\n"
            f"URL: {ctx.url}\n"
            f"Snippet: {ctx.snippet}\n"
        )
    return "\n".join(lines)


def _citations_from_contexts(
    contexts: List[RetrievedContext],
    cited_ids: Set[str],
) -> List[Citation]:
    citations = []
    for ctx in contexts:
        if cited_ids and ctx.id not in cited_ids:
            continue
        citations.append(
            Citation(
                source_id=ctx.id,
                url=ctx.url,
                title=ctx.title,
                quoted_span=ctx.snippet[:200],
            )
        )
    if not citations and contexts:
        citations = [
            Citation(
                source_id=c.id,
                url=c.url,
                title=c.title,
                quoted_span=c.snippet[:200],
            )
            for c in contexts
        ]
    return citations


def _extract_cited_ids(body: str, contexts: List[RetrievedContext]) -> Set[str]:
    ids = set(re.findall(r"\[(src-\d+|pplx-\d+)\]", body))
    valid = {c.id for c in contexts}
    return ids & valid if ids else {c.id for c in contexts}


def _llm_draft(query: str, contexts: List[RetrievedContext], stakes: str) -> DraftAnswer:
    model = get_chat_model().with_structured_output(DraftLLMOutput)
    sources_block = _format_sources_block(contexts)
    user_msg = (
        f"Stakes level: {stakes}\n"
        f"User question: {query}\n\n"
        f"SOURCES (cite using [src-N] IDs only):\n{sources_block}\n\n"
        "Write a complete, well-structured answer in your own words (2–4 short paragraphs). "
        "Use ONLY the sources above for factual claims. Do not paste raw markdown headings from snippets. "
        "Include inline [src-N] citations for major facts. "
        "If sources conflict, note the uncertainty."
    )
    result: DraftLLMOutput = model.invoke(
        [
            {"role": "system", "content": MASTER_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
    )
    cited = set(result.cited_source_ids) or _extract_cited_ids(result.body, contexts)
    return DraftAnswer(
        body=result.body,
        inline_citations=_citations_from_contexts(contexts, cited),
    )


def _plain_llm_draft(query: str, contexts: List[RetrievedContext], stakes: str) -> DraftAnswer:
    """Fallback when structured output fails (e.g. provider JSON limits)."""
    model = get_chat_model()
    sources_block = _format_sources_block(contexts)
    user_msg = (
        f"Stakes level: {stakes}\n"
        f"User question: {query}\n\n"
        f"SOURCES:\n{sources_block}\n\n"
        "Write a complete answer in plain prose with [src-N] citations. "
        "Do not copy markdown headings from snippets."
    )
    response = model.invoke(
        [
            {"role": "system", "content": MASTER_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]
    )
    body = response.content if hasattr(response, "content") else str(response)
    cited = _extract_cited_ids(body, contexts)
    return DraftAnswer(
        body=body.strip(),
        inline_citations=_citations_from_contexts(contexts, cited),
    )


def _template_draft(query: str, contexts: List[RetrievedContext]) -> DraftAnswer:
    """Fallback when LLM is unavailable but sources exist."""
    parts = []
    for ctx in contexts[:3]:
        snippet = re.sub(r"^#+\s*", "", ctx.snippet).strip()
        snippet = snippet[:280] + ("..." if len(ctx.snippet) > 280 else "")
        parts.append(f"- {snippet} [{ctx.id}]")
    body = (
        f"**{query}** — summary from retrieved sources:\n\n"
        + "\n".join(parts)
        + "\n\n"
        "_Note: LLM drafting failed — check LLM_MODEL matches your provider "
        "(e.g. use `llama-3.3-70b-versatile` for Groq, not `gpt-4o-mini`)._"
    )
    return DraftAnswer(
        body=body,
        inline_citations=_citations_from_contexts(contexts, {c.id for c in contexts}),
    )


def draft_node(state: AgentState) -> dict:
    query = state.get("query") or ""
    contexts = state.get("contexts") or []
    stakes = state.get("stakes") or "medium"

    if not contexts:
        draft = DraftAnswer(body=INSUFFICIENT_MSG, inline_citations=[])
        return {"draft": draft}

    if is_llm_available():
        try:
            draft = _llm_draft(query, contexts, stakes)
            return {"draft": draft}
        except Exception:
            try:
                draft = _plain_llm_draft(query, contexts, stakes)
                return {"draft": draft}
            except Exception:
                pass

    draft = _template_draft(query, contexts)
    return {"draft": draft}
