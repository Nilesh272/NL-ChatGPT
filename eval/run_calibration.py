"""Per-claim confidence vs verifier verdict calibration report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.config.settings import get_settings

from eval.schemas import ItemEvalResult


def build_calibration_report(results: List[ItemEvalResult]) -> Dict[str, Any]:
    """Analyze mismatches between confidence scores and verdicts."""
    settings = get_settings()
    rows: List[dict] = []
    mismatches: List[dict] = []

    for r in results:
        if not r.ok:
            continue
        for c in r.claims_detail:
            row = {
                "item_id": r.item_id,
                "claim_id": c.get("id"),
                "confidence": c.get("confidence"),
                "verdict": c.get("verdict"),
            }
            rows.append(row)
            conf = c.get("confidence", 5)
            verdict = c.get("verdict", "partial")
            high_but_bad = conf >= settings.confidence_threshold_high and verdict in (
                "unsupported",
                "contradicted",
            )
            low_but_good = conf <= settings.confidence_threshold_medium and verdict == "supported"
            if high_but_bad or low_but_good:
                mismatches.append({**row, "issue": "high_conf_bad_verdict" if high_but_bad else "low_conf_good_verdict"})

    by_verdict: Dict[str, List[int]] = {}
    for row in rows:
        by_verdict.setdefault(row["verdict"], []).append(row["confidence"])

    summary = {
        "total_claims": len(rows),
        "mismatch_count": len(mismatches),
        "mismatch_rate": len(mismatches) / len(rows) if rows else 0.0,
        "avg_confidence_by_verdict": {
            v: round(sum(cs) / len(cs), 2) for v, cs in by_verdict.items()
        },
        "thresholds": {
            "high": settings.confidence_threshold_high,
            "medium": settings.confidence_threshold_medium,
        },
        "recommendations": _threshold_recommendations(mismatches, rows, settings),
        "mismatches_sample": mismatches[:20],
    }
    return summary


def _threshold_recommendations(mismatches: list, rows: list, settings) -> List[str]:
    recs = []
    if not rows:
        return ["Run eval on more items to calibrate thresholds."]

    mismatch_rate = len(mismatches) / len(rows)
    if mismatch_rate > 0.25:
        recs.append(
            f"High mismatch rate ({mismatch_rate:.0%}): consider raising CONFIDENCE_THRESHOLD_HIGH "
            f"from {settings.confidence_threshold_high} to {min(10, settings.confidence_threshold_high + 1)}."
        )
    if mismatch_rate < 0.05:
        recs.append(
            "Low mismatch rate: current thresholds align well with verifier verdicts."
        )

    high_bad = sum(1 for m in mismatches if m.get("issue") == "high_conf_bad_verdict")
    if high_bad > 2:
        recs.append(
            "Several high-confidence claims were unsupported — tighten MiniCheck or verifier prompts."
        )

    recs.append(
        "Document chosen values in README after each eval run; re-run when changing LLM provider."
    )
    return recs


def write_calibration(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
