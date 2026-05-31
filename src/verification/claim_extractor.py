"""Extract atomic claims from a draft for verification."""

from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, Field

from src.llm.client import get_chat_model, is_llm_available
from src.models.schemas import Claim, ClaimVerdict, RetrievedContext
from src.prompts.templates import VERIFIER_PROMPT


class ExtractedClaim(BaseModel):
    id: str
    text: str


class ClaimExtractionResult(BaseModel):
    claims: List[ExtractedClaim] = Field(min_length=1)


_SKIP_PHRASES = (
    "summarized for:",
    "enable openai_api_key",
    "verification note:",
    "after verification,",
    "justification panel",
    "do not have enough verified information",
)


def _should_skip_chunk(chunk: str) -> bool:
    lower = chunk.lower()
    return any(p in lower for p in _SKIP_PHRASES)


def _heuristic_extract(body: str, max_claims: int = 8) -> List[ExtractedClaim]:
    """Split draft into verifiable claim sentences."""
    text = body.strip()
    if not text:
        return [ExtractedClaim(id="claim-1", text="(empty draft)")]

    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    claims: List[ExtractedClaim] = []
    for i, chunk in enumerate(chunks):
        chunk = re.sub(r"\[(src-|pplx-)\d+\]", "", chunk).strip()
        chunk = re.sub(r"\s+", " ", chunk)
        if len(chunk) < 15:
            continue
        if "do not have enough information" in chunk.lower():
            continue
        if _should_skip_chunk(chunk):
            continue
        claims.append(ExtractedClaim(id=f"claim-{len(claims) + 1}", text=chunk[:400]))
        if len(claims) >= max_claims:
            break

    if not claims:
        claims.append(ExtractedClaim(id="claim-1", text=text[:400]))
    return claims


def _llm_extract(body: str, query: str) -> List[ExtractedClaim]:
    model = get_chat_model(temperature=0.0).with_structured_output(ClaimExtractionResult)
    prompt = (
        f"{VERIFIER_PROMPT}\n\n"
        f"TASK: Extract atomic factual claims from the DRAFT below (max 8). "
        f"Each claim must be a single verifiable statement. Skip meta/instruction text.\n\n"
        f"User question: {query}\n\n"
        f"DRAFT:\n{body}"
    )
    result: ClaimExtractionResult = model.invoke(prompt)
    return result.claims


def extract_claims(
    draft_body: str,
    query: str = "",
    contexts: Optional[List[RetrievedContext]] = None,
) -> List[ExtractedClaim]:
    """Extract claims via LLM when available, else heuristics."""
    _ = contexts  # reserved for future context-aware extraction
    if is_llm_available() and draft_body.strip():
        try:
            return _llm_extract(draft_body, query)
        except Exception:
            pass
    return _heuristic_extract(draft_body)


def to_claim_objects(
    extracted: List[ExtractedClaim],
    default_verdict: ClaimVerdict = ClaimVerdict.PARTIAL,
) -> List[Claim]:
    return [
        Claim(
            id=item.id,
            text=item.text,
            verdict=default_verdict,
            source_ids=[],
            confidence=5,
            rationale="Pending verification.",
        )
        for item in extracted
    ]
