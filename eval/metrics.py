"""Internal evaluation metrics + confidence calibration."""

from __future__ import annotations

from typing import List

from src.config.settings import get_settings
from eval.schemas import AggregateMetrics, EvalItem, ItemEvalResult

REFUSAL_PHRASES = (
    "do not have enough information",
    "do not have enough verified information",
    "insufficient information",
)


def _is_refusal(answer: str) -> bool:
    lower = answer.lower()
    return any(p in lower for p in REFUSAL_PHRASES)


def confidence_verdict_agreement(claims_detail: List[dict]) -> float:
    """
    Fraction of claims where confidence aligns with verdict:
    - high confidence (>=8) -> supported
    - low confidence (<=4) -> unsupported/contradicted
    """
    if not claims_detail:
        return 1.0
    settings = get_settings()
    aligned = 0
    for c in claims_detail:
        conf = c.get("confidence", 5)
        verdict = c.get("verdict", "partial")
        if conf >= settings.confidence_threshold_high and verdict == "supported":
            aligned += 1
        elif conf <= settings.confidence_threshold_medium and verdict in (
            "unsupported",
            "contradicted",
        ):
            aligned += 1
        elif settings.confidence_threshold_medium < conf < settings.confidence_threshold_high:
            aligned += 1  # medium band — partial is acceptable
        elif verdict == "partial":
            aligned += 1
    return aligned / len(claims_detail)


def heuristic_faithfulness(claims_detail: List[dict]) -> float:
    """Share of claims marked supported (proxy for faithfulness when Ragas unavailable)."""
    if not claims_detail:
        return 0.0
    supported = sum(1 for c in claims_detail if c.get("verdict") == "supported")
    return supported / len(claims_detail)


def aggregate_metrics(
    items: List[EvalItem],
    results: List[ItemEvalResult],
) -> AggregateMetrics:
    agg = AggregateMetrics()
    agg.total = len(results)
    if not results:
        return agg

    ok_results = [r for r in results if r.ok]
    agg.pipeline_success_rate = len(ok_results) / len(results)

    total_claims = sum(r.claim_count for r in ok_results)
    unsupported = sum(r.unsupported_claim_count for r in ok_results)
    agg.unsupported_claim_rate = (unsupported / total_claims) if total_claims else 0.0

    refine_count = sum(1 for r in ok_results if r.refine_triggered)
    agg.refine_trigger_rate = refine_count / len(ok_results) if ok_results else 0.0

    # Refusal accuracy on items that expect refuse
    refuse_items = {i.id for i in items if i.expected_behavior == "refuse"}
    refuse_results = [r for r in ok_results if r.item_id in refuse_items]
    if refuse_results:
        correct_refusals = sum(1 for r in refuse_results if r.refused)
        agg.refusal_accuracy = correct_refusals / len(refuse_results)

    all_claims = []
    for r in ok_results:
        all_claims.extend(r.claims_detail)
    agg.heuristic_faithfulness = heuristic_faithfulness(all_claims)
    agg.confidence_verdict_agreement = confidence_verdict_agreement(all_claims)
    agg.avg_citations = sum(r.citation_count for r in ok_results) / len(ok_results)

    return agg


def result_from_pipeline(item: EvalItem, pipeline_result) -> ItemEvalResult:
    """Build ItemEvalResult from src.ui.runner.PipelineResult."""
    from src.models.schemas import ClaimVerdict as CV

    out = ItemEvalResult(item_id=item.id, query=item.query, ok=pipeline_result.ok)
    if pipeline_result.error:
        out.error = pipeline_result.error
        return out

    j = pipeline_result.justification
    if not j:
        out.error = "no_justification"
        out.ok = False
        return out

    out.answer = j.answer
    out.citation_count = len(j.citations)
    out.claim_count = len(j.claims)
    out.refused = _is_refusal(j.answer)
    out.overall_confidence = j.overall_confidence.value

    report = pipeline_result.verification_report
    claims_src = report.claims if report and report.claims else (j.claims or [])
    if claims_src:
        out.claim_count = len(claims_src)
        out.unsupported_claim_count = sum(
            1 for c in claims_src if c.verdict in (CV.UNSUPPORTED, CV.CONTRADICTED)
        )
        out.claims_detail = [
            {
                "id": c.id,
                "text": c.text[:200],
                "verdict": c.verdict.value,
                "confidence": c.confidence,
                "source_ids": c.source_ids,
            }
            for c in claims_src
        ]

    # Count refine from steps
    refine_steps = sum(1 for s in pipeline_result.steps_completed if s == "refine")
    out.refine_iterations = refine_steps
    out.refine_triggered = refine_steps > 0

    return out


def check_targets(agg: AggregateMetrics) -> dict:
    """Compare against Phase 4 exit criteria targets."""
    return {
        "ragas_faithfulness_gte_0.75": (
            agg.ragas_faithfulness is None or agg.ragas_faithfulness >= 0.75
        ),
        "unsupported_claim_rate_lt_0.10": agg.unsupported_claim_rate < 0.10,
        "refine_trigger_rate_15_40": 0.15 <= agg.refine_trigger_rate <= 0.40
        if agg.refine_trigger_rate > 0
        else True,
        "heuristic_faithfulness_gte_0.75": agg.heuristic_faithfulness >= 0.75,
    }
