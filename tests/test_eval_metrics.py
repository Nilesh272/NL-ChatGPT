from eval.metrics import (
    aggregate_metrics,
    check_targets,
    confidence_verdict_agreement,
    heuristic_faithfulness,
)
from eval.schemas import AggregateMetrics, EvalItem, ItemEvalResult


def test_heuristic_faithfulness():
    claims = [
        {"verdict": "supported", "confidence": 9},
        {"verdict": "supported", "confidence": 8},
        {"verdict": "unsupported", "confidence": 2},
    ]
    assert abs(heuristic_faithfulness(claims) - 2 / 3) < 0.01


def test_confidence_verdict_agreement():
    claims = [
        {"verdict": "supported", "confidence": 9},
        {"verdict": "unsupported", "confidence": 3},
    ]
    score = confidence_verdict_agreement(claims)
    assert 0.5 <= score <= 1.0


def test_aggregate_unsupported_rate():
    items = [EvalItem(id="1", query="q")]
    results = [
        ItemEvalResult(
            item_id="1",
            query="q",
            ok=True,
            claim_count=4,
            unsupported_claim_count=1,
        )
    ]
    agg = aggregate_metrics(items, results)
    assert agg.unsupported_claim_rate == 0.25


def test_check_targets_pass_heuristic():
    agg = AggregateMetrics(
        unsupported_claim_rate=0.05,
        refine_trigger_rate=0.25,
        heuristic_faithfulness=0.8,
    )
    targets = check_targets(agg)
    assert targets["unsupported_claim_rate_lt_0.10"]
    assert targets["heuristic_faithfulness_gte_0.75"]


def test_refusal_accuracy():
    items = [
        EvalItem(id="a", query="fake", expected_behavior="refuse"),
        EvalItem(id="b", query="france", expected_behavior="answer"),
    ]
    results = [
        ItemEvalResult(item_id="a", query="fake", ok=True, refused=True),
        ItemEvalResult(item_id="b", query="france", ok=True, refused=False),
    ]
    agg = aggregate_metrics(items, results)
    assert agg.refusal_accuracy == 1.0
