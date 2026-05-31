"""Confidence band logic — ARCHITECTURE §10."""

from __future__ import annotations

from typing import List, Optional, Tuple

from src.config.settings import get_settings
from src.models.schemas import Claim, ClaimVerdict, ConfidenceBand


def compute_overall_band(
    claims: List[Claim],
    insufficient: bool = False,
) -> ConfidenceBand:
    if insufficient:
        return ConfidenceBand.LOW
    if not claims:
        return ConfidenceBand.MEDIUM
    if any(
        c.verdict in (ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTED) for c in claims
    ):
        return ConfidenceBand.LOW
    settings = get_settings()
    min_conf = min(c.confidence for c in claims)
    if min_conf >= settings.confidence_threshold_high:
        return ConfidenceBand.HIGH
    if min_conf >= settings.confidence_threshold_medium:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def claim_confidence_style(confidence: int) -> Tuple[str, str]:
    settings = get_settings()
    if confidence >= settings.confidence_threshold_high:
        return "High", "#1b7f4e"
    if confidence >= settings.confidence_threshold_medium:
        return "Medium", "#b8860b"
    return "Low", "#c0392b"


def review_banner(band: ConfidenceBand) -> Optional[str]:
    if band == ConfidenceBand.LOW:
        return (
            "Review before using — overall confidence is LOW. "
            "Verify sources and claims before acting on this answer."
        )
    if band == ConfidenceBand.MEDIUM:
        return (
            "Moderate confidence — check flagged claims and citations before high-stakes use."
        )
    return None
