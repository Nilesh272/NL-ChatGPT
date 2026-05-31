from typing import Optional, TypedDict

from src.models.schemas import (
    DraftAnswer,
    JustificationBundle,
    ProcessedQuery,
    RetrievedContext,
    VerificationPlan,
    VerificationReport,
)


class AgentState(TypedDict, total=False):
    """LangGraph state passed between nodes."""

    # User input
    query: str
    stakes: str

    # Pipeline artifacts
    processed_query: Optional[ProcessedQuery]
    verification_plan: Optional[VerificationPlan]
    contexts: list[RetrievedContext]
    retrieval_snapshot: Optional[dict]
    draft: Optional[DraftAnswer]
    verification_report: Optional[VerificationReport]
    verification_snapshot: Optional[dict]
    justification: Optional[JustificationBundle]

    # Control flow (Phase 2+)
    iteration: int
    unsupported_critical_count: int

    error: Optional[str]
