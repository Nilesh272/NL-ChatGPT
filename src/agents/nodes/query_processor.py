"""Parse, classify, and expand queries for retrieval."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from src.agents.state import AgentState
from src.llm.client import get_chat_model, is_llm_available
from src.models.schemas import IntentType, ProcessedQuery, StakesLevel


class QueryExpansionOutput(BaseModel):
    intent: IntentType = IntentType.FACTUAL
    retrieval_queries: List[str] = Field(
        description="1-3 diverse search queries to retrieve evidence",
        min_length=1,
        max_length=3,
    )
    requires_realtime: bool = True


def _heuristic_intent(query: str) -> IntentType:
    q = query.lower()
    if any(w in q for w in ("how to", "steps", "tutorial")):
        return IntentType.PROCEDURAL
    if any(w in q for w in ("compare", "analyze", "why", "pros and cons")):
        return IntentType.ANALYTICAL
    if any(w in q for w in ("write", "draft", "poem", "creative")):
        return IntentType.CREATIVE
    return IntentType.FACTUAL


def _heuristic_expansion(query: str, intent: IntentType) -> List[str]:
    queries = [query]
    if intent == IntentType.FACTUAL:
        if "ceo" in query.lower() or "current" in query.lower():
            queries.append(f"{query} official announcement 2025 2026")
        else:
            queries.append(f"{query} definition explanation")
    elif intent == IntentType.ANALYTICAL:
        queries.append(f"{query} expert analysis")
    return list(dict.fromkeys(queries))[:3]


def _llm_expand(query: str, stakes: StakesLevel) -> QueryExpansionOutput:
    model = get_chat_model().with_structured_output(QueryExpansionOutput)
    prompt = (
        f"User query: {query}\n"
        f"Stakes: {stakes.value}\n\n"
        "Produce 1-3 search queries to retrieve web evidence. "
        "For time-sensitive facts (CEO, prices, news), include a recency-focused query. "
        "Classify intent accurately."
    )
    return model.invoke(prompt)


def query_processor_node(state: AgentState) -> dict:
    query = (state.get("query") or "").strip()
    stakes_raw = (state.get("stakes") or "medium").lower()
    try:
        stakes = StakesLevel(stakes_raw)
    except ValueError:
        stakes = StakesLevel.MEDIUM

    if is_llm_available() and query:
        try:
            expanded = _llm_expand(query, stakes)
            processed = ProcessedQuery(
                original_query=query,
                retrieval_queries=expanded.retrieval_queries,
                intent=expanded.intent,
                stakes=stakes,
                requires_realtime=expanded.requires_realtime,
                requires_user_docs=False,
            )
            return {"processed_query": processed}
        except Exception:
            pass

    intent = _heuristic_intent(query)
    processed = ProcessedQuery(
        original_query=query,
        retrieval_queries=_heuristic_expansion(query, intent),
        intent=intent,
        stakes=stakes,
        requires_realtime=intent == IntentType.FACTUAL,
        requires_user_docs=False,
    )
    return {"processed_query": processed}
