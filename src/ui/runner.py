"""Run the agent pipeline with step events for the UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.agents.graph import build_graph
from src.models.schemas import (
    ConfidenceBand,
    JustificationBundle,
    RetrievedContext,
    VerificationPlan,
    VerificationReport,
)


StepCallback = Callable[[str, Dict[str, Any]], None]

STEP_LABELS = {
    "query_processor": "Processing query",
    "planner": "Building verification plan",
    "retrieve": "Retrieving sources",
    "draft": "Drafting grounded answer",
    "verify": "Verifying claims",
    "refine": "Refining answer",
    "justify": "Packaging justification",
}


@dataclass
class PipelineResult:
    query: str
    stakes: str
    justification: Optional[JustificationBundle] = None
    contexts: List[RetrievedContext] = field(default_factory=list)
    verification_plan: Optional[VerificationPlan] = None
    retrieval_snapshot: Dict[str, Any] = field(default_factory=dict)
    verification_report: Optional[VerificationReport] = None
    steps_completed: List[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.justification is not None


def _coerce_contexts(raw: Any) -> List[RetrievedContext]:
    if not raw:
        return []
    out = []
    for item in raw:
        if isinstance(item, RetrievedContext):
            out.append(item)
        elif isinstance(item, dict):
            out.append(RetrievedContext.model_validate(item))
    return out


def run_pipeline(
    query: str,
    stakes: str = "medium",
    on_step: Optional[StepCallback] = None,
    include_verify_loop: bool = True,
) -> PipelineResult:
    """
    Execute the LangGraph pipeline and return UI-friendly artifacts.
    Optional on_step(node_name, state_update) for progress UI.
    """
    result = PipelineResult(query=query, stakes=stakes)
    graph = build_graph(include_justify=True, include_verify_loop=include_verify_loop)
    initial = {
        "query": query,
        "stakes": stakes,
        "iteration": 0,
        "unsupported_critical_count": 0,
    }

    final_state: Dict[str, Any] = {}
    try:
        for chunk in graph.stream(initial):
            if not isinstance(chunk, dict):
                continue
            for node_name, state_update in chunk.items():
                if on_step:
                    on_step(node_name, state_update or {})
                result.steps_completed.append(node_name)
                if state_update:
                    final_state.update(state_update)
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    result.contexts = _coerce_contexts(final_state.get("contexts"))
    snap = final_state.get("retrieval_snapshot")
    if isinstance(snap, dict):
        result.retrieval_snapshot = snap

    plan = final_state.get("verification_plan")
    if plan:
        result.verification_plan = (
            VerificationPlan.model_validate(plan) if isinstance(plan, dict) else plan
        )

    report = final_state.get("verification_report")
    if report:
        result.verification_report = (
            VerificationReport.model_validate(report) if isinstance(report, dict) else report
        )

    just = final_state.get("justification")
    if just:
        result.justification = (
            JustificationBundle.model_validate(just) if isinstance(just, dict) else just
        )
    else:
        result.error = result.error or "Pipeline finished without justification."

    return result


def step_label(node_name: str) -> str:
    return STEP_LABELS.get(node_name, node_name.replace("_", " ").title())
