"""Human judgment UI helpers — export, gates, fellowship copy."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Optional

from src.models.judgment import TurnReview, UserClaimVerdict

if TYPE_CHECKING:
    from src.models.schemas import JustificationBundle

FELLOWSHIP_PILLARS = """
**How this assistant supports your judgment (not replaces it)**

1. **Output quality** — Review correctness, completeness, reasoning, usefulness, and uncertainty per claim.
2. **Human judgment** — You choose Trust / Unsure / Reject on each claim; the AI does not decide for you.
3. **Confidence calibration** — Scores flag what to double-check; low overall confidence means slow down.
4. **Legible reasoning** — Sources, assumptions, and gaps are visible before you act on the answer.
"""

VERDICT_LABELS = {
    UserClaimVerdict.TRUST: "Trust",
    UserClaimVerdict.UNSURE: "Unsure",
    UserClaimVerdict.REJECT: "Reject",
}


def stakes_requires_claim_review(stakes: str) -> bool:
    return stakes == "high"


def stakes_requires_signoff(stakes: str) -> bool:
    return stakes == "high"


def can_copy_or_export(stakes: str, turn_review: TurnReview) -> tuple[bool, str]:
    """Return (allowed, reason_if_blocked)."""
    if stakes_requires_claim_review(stakes) and not turn_review.meets_high_stakes_gate(1):
        return False, "Review at least one claim (Trust, Unsure, or Reject) before copying or exporting."
    if stakes_requires_signoff(stakes) and not turn_review.export_signed_off:
        return False, "Check the sign-off box confirming you reviewed this answer before exporting."
    return True, ""


def build_export_payload(
    bundle: "JustificationBundle",
    turn_review: TurnReview,
    query: str,
) -> dict:
    return {
        "query": query,
        "stakes": turn_review.stakes,
        "answer": bundle.answer,
        "overall_confidence": bundle.overall_confidence.value,
        "assumptions": bundle.assumptions,
        "gaps": bundle.gaps,
        "citations": [c.model_dump() for c in bundle.citations],
        "claims": [c.model_dump(mode="json") for c in bundle.claims],
        "user_claim_reviews": [r.model_dump(mode="json") for r in turn_review.claim_reviews],
        "rejected_by_user": [r.model_dump(mode="json") for r in turn_review.rejected_claims()],
        "export_signed_off": turn_review.export_signed_off,
        "signoff_statement": turn_review.signoff_statement,
        "disclaimer": "AI-assisted draft — human judgment required before high-stakes use.",
    }


def build_export_markdown(payload: dict) -> str:
    lines = [
        "# NL ChatGPT — Export with Human Review",
        "",
        f"**Query:** {payload.get('query', '')}",
        f"**Stakes:** {payload.get('stakes', '')}",
        f"**Overall confidence:** {payload.get('overall_confidence', '')}",
        f"**Signed off:** {payload.get('export_signed_off', False)}",
        "",
        "## Answer",
        "",
        payload.get("answer", ""),
        "",
        "## Your claim reviews",
        "",
    ]
    for r in payload.get("user_claim_reviews", []):
        lines.append(f"- **{r.get('claim_id')}**: {r.get('verdict')} — {r.get('note', '') or '(no note)'}")
    rejected = payload.get("rejected_by_user", [])
    if rejected:
        lines.append("")
        lines.append("## Claims you rejected")
        for r in rejected:
            lines.append(f"- {r.get('claim_id')}: {r.get('note', '')}")
    lines.append("")
    lines.append(f"_{payload.get('disclaimer', '')}_")
    return "\n".join(lines)


def build_export_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, default=str)
