"""Ragas evaluation — faithfulness, answer relevancy, context precision."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from eval.schemas import ItemEvalResult


def run_ragas_eval(
    results: List[ItemEvalResult],
    contexts_per_item: List[List[str]],
) -> Dict[str, Optional[float]]:
    """
    Run Ragas metrics when the package is installed and LLM keys are available.
    Returns dict with metric means or None if skipped.
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, faithfulness
    except ImportError:
        return {
            "ragas_faithfulness": None,
            "ragas_answer_relevancy": None,
            "ragas_context_precision": None,
            "skipped": "ragas not installed (pip install -e '.[eval]')",
        }

    from src.llm.client import is_llm_available

    if not is_llm_available():
        return {
            "ragas_faithfulness": None,
            "ragas_answer_relevancy": None,
            "ragas_context_precision": None,
            "skipped": "LLM API key required for Ragas",
        }

    ok = [r for r in results if r.ok and r.answer]
    if not ok:
        return {"skipped": "no successful results"}

    questions = [r.query for r in ok]
    answers = [r.answer for r in ok]
    contexts = []
    ctx_map = {r.item_id: ctxs for r, ctxs in zip(ok, contexts_per_item)}
    for r in ok:
        contexts.append(ctx_map.get(r.item_id, []) or ["No context retrieved."])

    try:
        dataset = Dataset.from_dict(
            {
                "question": questions,
                "answer": answers,
                "contexts": contexts,
            }
        )
        scores = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision],
        )
        df = scores.to_pandas()
        out: Dict[str, Any] = {}
        for col in ("faithfulness", "answer_relevancy", "context_precision"):
            if col in df.columns:
                out[f"ragas_{col}"] = float(df[col].mean())
        return out
    except Exception as exc:
        return {
            "ragas_faithfulness": None,
            "ragas_answer_relevancy": None,
            "ragas_context_precision": None,
            "skipped": f"ragas error: {exc}",
        }
