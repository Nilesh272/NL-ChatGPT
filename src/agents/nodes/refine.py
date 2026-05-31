"""Patch draft from verification report; increment refine iteration."""

from src.agents.state import AgentState
from src.models.schemas import DraftAnswer, RetrievedContext
from src.verification.refiner import refine_draft


def _format_sources(contexts: list) -> str:
    lines = []
    for ctx in contexts:
        if isinstance(ctx, dict):
            ctx = RetrievedContext.model_validate(ctx)
        lines.append(f"[{ctx.id}] {ctx.snippet}")
    return "\n".join(lines)


def refine_node(state: AgentState) -> dict:
    draft = state.get("draft")
    report = state.get("verification_report")
    contexts = state.get("contexts") or []
    query = state.get("query") or ""
    iteration = state.get("iteration") or 0

    if not draft or not report:
        return {"iteration": iteration + 1}

    if isinstance(draft, dict):
        draft = DraftAnswer.model_validate(draft)

    sources_block = _format_sources(contexts)
    ctx_models = []
    for c in contexts:
        if isinstance(c, dict):
            ctx_models.append(RetrievedContext.model_validate(c))
        else:
            ctx_models.append(c)

    refined = refine_draft(
        draft,
        report,
        query=query,
        sources_block=sources_block,
        contexts=ctx_models,
    )

    return {
        "draft": refined,
        "iteration": iteration + 1,
    }
