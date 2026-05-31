from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    FACTUAL = "factual"
    ANALYTICAL = "analytical"
    CREATIVE = "creative"
    PROCEDURAL = "procedural"


class StakesLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ConfidenceBand(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ClaimVerdict(str, Enum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"


class ProcessedQuery(BaseModel):
    original_query: str
    retrieval_queries: list[str] = Field(default_factory=list)
    intent: IntentType = IntentType.FACTUAL
    stakes: StakesLevel = StakesLevel.MEDIUM
    requires_realtime: bool = True
    requires_user_docs: bool = False


class RetrievedContext(BaseModel):
    id: str
    url: str
    title: str
    snippet: str
    published_at: Optional[str] = None
    relevance_score: float = Field(ge=0.0, le=1.0, default=0.0)


class Citation(BaseModel):
    source_id: str
    url: str
    title: str
    quoted_span: Optional[str] = None


class VerificationPlan(BaseModel):
    verification_plan: list[str] = Field(default_factory=list)
    retrieval_queries: list[str] = Field(default_factory=list)
    must_verify: list[str] = Field(default_factory=list)
    stop_conditions: list[str] = Field(default_factory=list)


class DraftAnswer(BaseModel):
    body: str
    inline_citations: list[Citation] = Field(default_factory=list)


class Claim(BaseModel):
    id: str
    text: str
    verdict: ClaimVerdict = ClaimVerdict.SUPPORTED
    source_ids: list[str] = Field(default_factory=list)
    confidence: int = Field(ge=1, le=10, default=7)
    rationale: str = ""


class VerificationReport(BaseModel):
    claims: list[Claim] = Field(default_factory=list)
    contradictions: list[dict] = Field(default_factory=list)
    recommended_edits: list[str] = Field(default_factory=list)
    unsupported_critical_count: int = 0


class JustificationBundle(BaseModel):
    answer: str
    claims: list[Claim] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    overall_confidence: ConfidenceBand = ConfidenceBand.MEDIUM
    citations: list[Citation] = Field(default_factory=list)
    verify_checklist: list[str] = Field(default_factory=list)
    verification_plan: list[str] = Field(default_factory=list)
    phase: str = "0-stub"


class SessionMessage(BaseModel):
    message_id: str
    role: str
    content: str
    justification: Optional[JustificationBundle] = None
