"""Lightweight claim–passage entailment (MiniCheck-style heuristic).

Runs on claims where LLM verifier confidence is below threshold to reduce cost.
Optional: set MINICHECK_MODEL_PATH for a future HF model integration.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from src.config.settings import get_settings

_STOPWORDS = frozenset(
    "a an the is are was were be been being have has had do does did will would "
    "can could should may might must of in on at to for with by from as and or but "
    "not no it its this that these those".split()
)


def _tokenize(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _numbers(text: str) -> set:
    return set(re.findall(r"\b\d+(?:\.\d+)?\b", text))


def entailment_score(claim: str, passage: str) -> float:
    """
    Score in [0, 1]: higher means passage better supports the claim.
    Heuristic: token overlap + number consistency + penalize novel entities.
    """
    if not claim.strip() or not passage.strip():
        return 0.0

    claim_tokens = _tokenize(claim)
    passage_tokens = _tokenize(passage)
    if not claim_tokens:
        return 0.5

    overlap = claim_tokens & passage_tokens
    overlap_ratio = len(overlap) / len(claim_tokens)

    claim_nums = _numbers(claim)
    passage_nums = _numbers(passage)
    num_penalty = 0.0
    if claim_nums and passage_nums and not claim_nums <= passage_nums:
        num_penalty = 0.35
    elif claim_nums and not passage_nums:
        num_penalty = 0.2

    # Proper nouns in claim absent from passage
    claim_caps = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?", claim))
    passage_lower = passage.lower()
    cap_miss = sum(1 for c in claim_caps if c.lower() not in passage_lower)
    cap_penalty = min(0.3, cap_miss * 0.1)

    score = overlap_ratio - num_penalty - cap_penalty
    return max(0.0, min(1.0, score))


def batch_check(
    claim: str,
    passages: List[Tuple[str, str]],
) -> Tuple[float, Optional[str], Optional[str]]:
    """
    Check claim against multiple (source_id, passage) pairs.
    Returns (best_score, best_source_id, best_quote_span).
    """
    best_score = 0.0
    best_id: Optional[str] = None
    best_quote: Optional[str] = None

    for source_id, passage in passages:
        score = entailment_score(claim, passage)
        if score > best_score:
            best_score = score
            best_id = source_id
            best_quote = passage[:200]

    return best_score, best_id, best_quote


def score_to_confidence(score: float) -> int:
    """Map entailment score to 1–10 confidence."""
    if score >= 0.65:
        return 8
    if score >= 0.45:
        return 6
    if score >= 0.25:
        return 4
    return 2


def score_to_verdict(score: float) -> str:
    settings = get_settings()
    if score >= 0.55:
        return "supported"
    if score >= 0.3:
        return "partial"
    return "unsupported"


def is_minicheck_enabled() -> bool:
    """Heuristic MiniCheck always available; HF path optional later."""
    return True
