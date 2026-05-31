"""DeepEval metrics — hallucination, contextual recall (optional)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from eval.schemas import ItemEvalResult


def run_deepeval_metrics(
    results: List[ItemEvalResult],
    contexts_per_item: List[List[str]],
) -> Dict[str, Optional[float]]:
    """Run DeepEval when installed; otherwise return skip reason."""
    try:
        from deepeval.metrics import (
            ContextualRecallMetric,
            HallucinationMetric,
        )
        from deepeval.test_case import LLMTestCase
    except ImportError:
        return {
            "deepeval_hallucination": None,
            "deepeval_contextual_recall": None,
            "skipped": "deepeval not installed (pip install -e '.[eval]')",
        }

    from src.llm.client import is_llm_available

    if not is_llm_available():
        return {
            "deepeval_hallucination": None,
            "deepeval_contextual_recall": None,
            "skipped": "LLM API key required for DeepEval",
        }

    ok_pairs = [
        (r, ctxs)
        for r, ctxs in zip(results, contexts_per_item)
        if r.ok and r.answer and ctxs
    ]
    if not ok_pairs:
        return {"skipped": "no results with context for DeepEval"}

    hallucination_metric = HallucinationMetric(threshold=0.5)
    recall_metric = ContextualRecallMetric(threshold=0.5)

    hall_scores = []
    recall_scores = []

    for r, ctxs in ok_pairs[:10]:  # cap cost for prototype
        context_str = "\n".join(ctxs)
        case = LLMTestCase(
            input=r.query,
            actual_output=r.answer,
            context=[context_str],
        )
        try:
            hallucination_metric.measure(case)
            hall_scores.append(hallucination_metric.score or 0.0)
        except Exception:
            pass
        try:
            recall_metric.measure(case)
            recall_scores.append(recall_metric.score or 0.0)
        except Exception:
            pass

    out: Dict[str, Any] = {}
    if hall_scores:
        out["deepeval_hallucination"] = sum(hall_scores) / len(hall_scores)
    if recall_scores:
        out["deepeval_contextual_recall"] = sum(recall_scores) / len(recall_scores)
    return out
