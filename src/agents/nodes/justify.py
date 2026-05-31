"""Package final justification bundle using verification report."""

from __future__ import annotations

from typing import Optional

from src.agents.state import AgentState
from src.config.settings import get_settings
from src.models.schemas import (
    Citation,
    Claim,
    ClaimVerdict,
    ConfidenceBand,
    JustificationBundle,
    VerificationReport,
)
from src.models.confidence import compute_overall_band


def justify_node(state: AgentState) -> dict:
    draft = state.get("draft")
    contexts = state.get("contexts") or []
    plan = state.get("verification_plan")
    snapshot = state.get("retrieval_snapshot") or {}
    report_raw = state.get("verification_report")
    query = state.get("query", "")
    iteration = state.get("iteration") or 0

    report: Optional[VerificationReport] = None
    if report_raw:
        report = (
            VerificationReport.model_validate(report_raw)
            if isinstance(report_raw, dict)
            else report_raw
        )

    answer = draft.body if draft else "No draft available."
    citations = list(draft.inline_citations) if draft and draft.inline_citations else []

    if not citations and contexts:
        citations = [
            Citation(source_id=c.id, url=c.url, title=c.title, quoted_span=c.snippet[:120])
            for c in contexts
        ]

    insufficient = "do not have enough information" in answer.lower()
    claims: list[Claim] = list(report.claims) if report and report.claims else []

    provider = snapshot.get("provider", "unknown")
    gaps = []
    if insufficient:
        gaps.append("No relevant sources retrieved — answer intentionally withheld.")
    if provider == "mock":
        gaps.append("Using mock retrieval — set TAVILY_API_KEY for live web search.")
    if snapshot.get("errors"):
        gaps.append(f"Retrieval issues: {snapshot.get('errors')}")
    if report:
        unsupported = [c for c in report.claims if c.verdict == ClaimVerdict.UNSUPPORTED]
        contradicted = [c for c in report.claims if c.verdict == ClaimVerdict.CONTRADICTED]
        if unsupported:
            gaps.append(f"{len(unsupported)} claim(s) marked unsupported by verifier.")
        if contradicted:
            gaps.append(f"{len(contradicted)} claim(s) marked contradicted by verifier.")
        if report.recommended_edits:
            gaps.extend(report.recommended_edits[:3])
    if iteration > 0:
        gaps.append(f"Draft refined {iteration} time(s) after verification.")

    verify_checklist = [
        "Open each citation URL and confirm snippets support the answer.",
        "Review claims marked unsupported or partial before acting on the answer.",
        "For time-sensitive facts, confirm publication dates on sources.",
    ]
    if claims:
        low_conf = [c for c in claims if c.confidence < get_settings().confidence_threshold_high]
        if low_conf:
            verify_checklist.append(
                f"Manually verify {len(low_conf)} claim(s) with confidence below "
                f"{get_settings().confidence_threshold_high}/10."
            )

    overall = compute_overall_band(claims, insufficient=insufficient)

    justification = JustificationBundle(
        answer=answer,
        claims=claims,
        assumptions=[
            f"Query: {query[:120]}",
            f"Retrieval provider: {provider}",
            f"Verify/refine iterations: {iteration}",
        ],
        gaps=gaps,
        overall_confidence=overall,
        citations=citations,
        verify_checklist=verify_checklist,
        verification_plan=plan.verification_plan if plan else [],
        phase="5-judgment",
    )
    return {"justification": justification}
