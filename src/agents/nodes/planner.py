"""CoT verification plan — LLM structured output with heuristic fallback."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from src.agents.state import AgentState
from src.llm.client import get_chat_model, is_llm_available
from src.models.schemas import VerificationPlan
from src.prompts.templates import PLANNER_PROMPT


class PlannerOutput(BaseModel):
    verification_plan: List[str] = Field(min_length=3, max_length=8)
    retrieval_queries: List[str] = Field(default_factory=list)
    must_verify: List[str] = Field(min_length=1)
    stop_conditions: List[str] = Field(min_length=1)


def _stub_plan(query: str, retrieval_queries: List[str]) -> VerificationPlan:
    return VerificationPlan(
        verification_plan=[
            "1. List factual claims required to answer the query.",
            "2. Retrieve external sources for each claim.",
            "3. Draft answer citing source IDs only (e.g. [src-1]).",
            "4. Flag unsupported or contradictory claims.",
            "5. Package citations and human verify checklist.",
        ],
        retrieval_queries=retrieval_queries or [query],
        must_verify=[
            "Every factual statement maps to at least one retrieved source.",
            "Time-sensitive facts use recent sources.",
        ],
        stop_conditions=[
            "If no relevant sources are retrieved, refuse or narrow the answer.",
            "Do not guess when evidence is insufficient.",
        ],
    )


def planner_node(state: AgentState) -> dict:
    processed = state.get("processed_query")
    query = processed.original_query if processed else (state.get("query") or "")
    retrieval_queries = (
        processed.retrieval_queries if processed else ([query] if query else [])
    )
    stakes = processed.stakes.value if processed else state.get("stakes", "medium")

    if is_llm_available() and query:
        try:
            model = get_chat_model().with_structured_output(PlannerOutput)
            result: PlannerOutput = model.invoke(
                f"{PLANNER_PROMPT}\n\n"
                f"User query: {query}\n"
                f"Stakes: {stakes}\n"
                f"Suggested retrieval queries: {retrieval_queries}\n"
            )
            merged_queries = list(
                dict.fromkeys(result.retrieval_queries or retrieval_queries)
            )[:3]
            plan = VerificationPlan(
                verification_plan=result.verification_plan,
                retrieval_queries=merged_queries,
                must_verify=result.must_verify,
                stop_conditions=result.stop_conditions,
            )
            if processed and merged_queries:
                processed = processed.model_copy(
                    update={"retrieval_queries": merged_queries}
                )
                return {"verification_plan": plan, "processed_query": processed}
            return {"verification_plan": plan}
        except Exception:
            pass

    plan = _stub_plan(query, retrieval_queries)
    return {"verification_plan": plan}
