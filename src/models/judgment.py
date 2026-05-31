"""User judgment models — Phase 5 human-in-the-loop."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class UserClaimVerdict(str, Enum):
    TRUST = "trust"
    UNSURE = "unsure"
    REJECT = "reject"


class ClaimReview(BaseModel):
    claim_id: str
    verdict: UserClaimVerdict
    note: str = ""
    reviewed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class TurnReview(BaseModel):
    """User reviews for one assistant turn."""

    session_id: str
    turn_id: str
    query: str = ""
    stakes: str = "medium"
    claim_reviews: List[ClaimReview] = Field(default_factory=list)
    export_signed_off: bool = False
    signoff_statement: str = ""

    def reviewed_claim_ids(self) -> List[str]:
        return [r.claim_id for r in self.claim_reviews]

    def rejected_claims(self) -> List[ClaimReview]:
        return [r for r in self.claim_reviews if r.verdict == UserClaimVerdict.REJECT]

    def has_interacted(self) -> bool:
        return len(self.claim_reviews) > 0

    def meets_high_stakes_gate(self, min_reviews: int = 1) -> bool:
        return len(self.claim_reviews) >= min_reviews
