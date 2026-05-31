from src.models.schemas import Claim, ClaimVerdict, ConfidenceBand
from src.models.confidence import compute_overall_band, review_banner
from src.ui.runner import PipelineResult, run_pipeline, step_label


def test_compute_overall_band_low_on_unsupported():
    claims = [
        Claim(
            id="c1",
            text="False fact",
            verdict=ClaimVerdict.UNSUPPORTED,
            confidence=3,
        ),
        Claim(id="c2", text="Ok", verdict=ClaimVerdict.SUPPORTED, confidence=9),
    ]
    assert compute_overall_band(claims) == ConfidenceBand.LOW


def test_compute_overall_band_high_when_all_strong():
    claims = [
        Claim(id="c1", text="A", verdict=ClaimVerdict.SUPPORTED, confidence=9),
        Claim(id="c2", text="B", verdict=ClaimVerdict.SUPPORTED, confidence=8),
    ]
    assert compute_overall_band(claims) == ConfidenceBand.HIGH


def test_review_banner_low():
    msg = review_banner(ConfidenceBand.LOW)
    assert msg is not None
    assert "Review before using" in msg


def test_run_pipeline_mock_mode():
    result = run_pipeline("What is Agentic RAG?", stakes="medium")
    assert isinstance(result, PipelineResult)
    assert result.ok
    assert result.justification is not None
    assert result.justification.phase in ("3-ui", "5-judgment")
    assert len(result.justification.citations) >= 1
    assert "query_processor" in result.steps_completed


def test_step_labels():
    assert "Retrieving" in step_label("retrieve") or "retrieving" in step_label("retrieve").lower()
