from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvalItem:
    id: str
    query: str
    expects_sources: bool = True
    expected_behavior: str = "answer"  # answer | refuse
    stakes: str = "medium"
    ground_truth: str = ""
    reference_urls: List[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class ItemEvalResult:
    item_id: str
    query: str
    ok: bool
    answer: str = ""
    citation_count: int = 0
    claim_count: int = 0
    unsupported_claim_count: int = 0
    refine_iterations: int = 0
    refine_triggered: bool = False
    refused: bool = False
    overall_confidence: str = ""
    error: Optional[str] = None
    claims_detail: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AggregateMetrics:
    total: int = 0
    pipeline_success_rate: float = 0.0
    unsupported_claim_rate: float = 0.0
    refine_trigger_rate: float = 0.0
    refusal_accuracy: float = 0.0
    heuristic_faithfulness: float = 0.0
    confidence_verdict_agreement: float = 0.0
    avg_citations: float = 0.0
    ragas_faithfulness: Optional[float] = None
    ragas_answer_relevancy: Optional[float] = None
    ragas_context_precision: Optional[float] = None
    deepeval_hallucination: Optional[float] = None
    deepeval_contextual_recall: Optional[float] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}
