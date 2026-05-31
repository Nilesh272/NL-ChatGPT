"""
Run full Phase 4 evaluation suite.

  python -m eval.run_all
  python -m eval.run_all --limit 5
  python -m eval.run_all --skip-ragas --skip-deepeval
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from eval.load_dataset import load_dataset
from eval.metrics import aggregate_metrics, check_targets, result_from_pipeline
from eval.run_calibration import build_calibration_report, write_calibration
from eval.run_deepeval import run_deepeval_metrics
from eval.run_ragas import run_ragas_eval
from eval.schemas import ItemEvalResult

RESULTS_DIR = Path(__file__).parent / "results"


def _run_batch(limit: int = 0) -> tuple[list, list[ItemEvalResult], list]:
    from src.ui.runner import run_pipeline

    items = load_dataset(limit=limit)
    results: list[ItemEvalResult] = []
    pipeline_outputs = []
    contexts_per_item = []

    for i, item in enumerate(items):
        print(f"[{i + 1}/{len(items)}] {item.id}: {item.query[:60]}...")
        pr = run_pipeline(query=item.query, stakes=item.stakes)
        pipeline_outputs.append(pr)
        contexts_per_item.append([c.snippet for c in pr.contexts])
        results.append(result_from_pipeline(item, pr))

    return items, results, contexts_per_item


def _write_summary_md(agg, targets: dict, ragas: dict, deepeval: dict, calibration: dict) -> str:
    lines = [
        "# Evaluation Summary (Phase 4)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Internal metrics",
        "",
        f"| Metric | Value | Target |",
        f"|--------|-------|--------|",
        f"| Pipeline success rate | {agg.pipeline_success_rate:.1%} | — |",
        f"| Unsupported claim rate | {agg.unsupported_claim_rate:.1%} | < 10% |",
        f"| Refine trigger rate | {agg.refine_trigger_rate:.1%} | 15–40% |",
        f"| Heuristic faithfulness | {agg.heuristic_faithfulness:.2f} | ≥ 0.75 |",
        f"| Confidence–verdict agreement | {agg.confidence_verdict_agreement:.1%} | — |",
        f"| Refusal accuracy | {agg.refusal_accuracy:.1%} | — |",
        f"| Avg citations | {agg.avg_citations:.1f} | ≥ 3 |",
        "",
        "## Ragas (optional)",
        "",
    ]
    if agg.ragas_faithfulness is not None:
        lines.append(f"- Faithfulness: **{agg.ragas_faithfulness:.3f}** (target ≥ 0.75)")
    else:
        lines.append(f"- Skipped: {ragas.get('skipped', 'N/A')}")
    if agg.ragas_answer_relevancy is not None:
        lines.append(f"- Answer relevancy: {agg.ragas_answer_relevancy:.3f}")
    if agg.ragas_context_precision is not None:
        lines.append(f"- Context precision: {agg.ragas_context_precision:.3f}")

    lines.extend(["", "## DeepEval (optional)", ""])
    if agg.deepeval_hallucination is not None:
        lines.append(f"- Hallucination score: {agg.deepeval_hallucination:.3f}")
    else:
        lines.append(f"- Skipped: {deepeval.get('skipped', 'N/A')}")

    lines.extend(["", "## Target checks", ""])
    for k, v in targets.items():
        lines.append(f"- {'✅' if v else '⚠️'} `{k}`")

    lines.extend(["", "## Threshold recommendations", ""])
    for rec in calibration.get("recommendations", []):
        lines.append(f"- {rec}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="NL ChatGPT Phase 4 evaluation")
    parser.add_argument("--limit", type=int, default=0, help="Max dataset items (0 = all)")
    parser.add_argument("--skip-ragas", action="store_true")
    parser.add_argument("--skip-deepeval", action="store_true")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    items, results, contexts_per_item = _run_batch(limit=args.limit)
    agg = aggregate_metrics(items, results)

    ragas_out = {}
    if not args.skip_ragas:
        print("Running Ragas...")
        ragas_out = run_ragas_eval(results, contexts_per_item)
        agg.ragas_faithfulness = ragas_out.get("ragas_faithfulness")
        agg.ragas_answer_relevancy = ragas_out.get("ragas_answer_relevancy")
        agg.ragas_context_precision = ragas_out.get("ragas_context_precision")

    deepeval_out = {}
    if not args.skip_deepeval:
        print("Running DeepEval...")
        deepeval_out = run_deepeval_metrics(results, contexts_per_item)
        agg.deepeval_hallucination = deepeval_out.get("deepeval_hallucination")
        agg.deepeval_contextual_recall = deepeval_out.get("deepeval_contextual_recall")

    calibration = build_calibration_report(results)
    targets = check_targets(agg)

    # Write artifacts
    per_item_path = RESULTS_DIR / "per_item.jsonl"
    with open(per_item_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r.__dict__, default=str) + "\n")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_size": len(items),
        "metrics": agg.to_dict(),
        "targets_met": targets,
        "ragas": ragas_out,
        "deepeval": deepeval_out,
        "calibration_summary": {
            "mismatch_rate": calibration.get("mismatch_rate"),
            "recommendations": calibration.get("recommendations"),
        },
    }
    with open(RESULTS_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    write_calibration(RESULTS_DIR / "calibration.json", calibration)

    md = _write_summary_md(agg, targets, ragas_out, deepeval_out, calibration)
    with open(RESULTS_DIR / "summary.md", "w", encoding="utf-8") as f:
        f.write(md)

    print("\n" + md)
    print(f"\nResults written to {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
