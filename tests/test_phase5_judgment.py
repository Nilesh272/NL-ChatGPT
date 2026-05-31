import tempfile
from pathlib import Path

from src.models.judgment import TurnReview, UserClaimVerdict
from src.storage.judgment_store import JudgmentStore
from src.ui.judgment import can_copy_or_export, stakes_requires_claim_review


def test_high_stakes_requires_review():
    assert stakes_requires_claim_review("high")
    assert not stakes_requires_claim_review("low")


def test_copy_blocked_without_review():
    review = TurnReview(session_id="s1", turn_id="t1", stakes="high")
    allowed, reason = can_copy_or_export("high", review)
    assert not allowed
    assert "at least one claim" in reason.lower()


def test_copy_allowed_after_review_and_signoff():
    from src.models.judgment import ClaimReview

    review = TurnReview(
        session_id="s1",
        turn_id="t1",
        stakes="high",
        claim_reviews=[
            ClaimReview(claim_id="c1", verdict=UserClaimVerdict.TRUST),
        ],
        export_signed_off=True,
    )
    allowed, _ = can_copy_or_export("high", review)
    assert allowed


def test_judgment_store_persist_and_reject_list():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "test.db"
        store = JudgmentStore(db_path=db)
        store.upsert_claim_review(
            "sess", "turn1", "claim-1", UserClaimVerdict.REJECT, note="wrong metric"
        )
        store.upsert_claim_review("sess", "turn1", "claim-2", UserClaimVerdict.TRUST)
        turn = store.get_turn_reviews("sess", "turn1")
        assert len(turn.claim_reviews) == 2
        assert turn.rejected_claims()[0].claim_id == "claim-1"
        rejected = store.list_rejected_for_session("sess")
        assert len(rejected) == 1
        assert rejected[0]["claim_id"] == "claim-1"


def test_low_stakes_no_gate():
    review = TurnReview(session_id="s", turn_id="t", stakes="low")
    allowed, _ = can_copy_or_export("low", review)
    assert allowed
