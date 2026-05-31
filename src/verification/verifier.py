"""Verify draft claims against retrieved sources."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from src.config.settings import get_settings
from src.llm.client import get_chat_model, is_llm_available
from src.models.schemas import (
    Claim,
    ClaimVerdict,
    DraftAnswer,
    RetrievedContext,
    VerificationReport,
)
from src.prompts.templates import VERIFIER_PROMPT
from src.verification.claim_extractor import extract_claims, to_claim_objects
from src.verification.minicheck import batch_check, score_to_confidence, score_to_verdict


class LLMClaimVerdict(BaseModel):
    id: str
    text: str
    verdict: ClaimVerdict
    source_ids: List[str] = Field(default_factory=list)
    supporting_quote: str = ""
    confidence: int = Field(ge=1, le=10)
    rationale: str = ""


class LLMVerificationOutput(BaseModel):
    claims: List[LLMClaimVerdict] = Field(default_factory=list)
    contradictions: List[dict] = Field(default_factory=list)
    recommended_edits: List[str] = Field(default_factory=list)


def _sources_block(contexts: List[RetrievedContext]) -> str:
    lines = []
    for ctx in contexts:
        lines.append(f"[{ctx.id}] {ctx.title}\nURL: {ctx.url}\n{ctx.snippet}\n")
    return "\n".join(lines)


def _context_by_id(contexts: List[RetrievedContext]) -> Dict[str, RetrievedContext]:
    return {c.id: c for c in contexts}


def _cited_passages(claim_text: str, contexts: List[RetrievedContext]) -> List[tuple]:
    by_id = _context_by_id(contexts)
    cited_ids = re.findall(r"\[(src-\d+|pplx-\d+)\]", claim_text)
    if cited_ids:
        return [(sid, by_id[sid].snippet) for sid in cited_ids if sid in by_id]
    return [(c.id, c.snippet) for c in contexts]


def _heuristic_verify_claim(claim_text: str, contexts: List[RetrievedContext]) -> Claim:
    passages = _cited_passages(claim_text, contexts)
    score, source_id, quote = batch_check(claim_text, passages)
    verdict_str = score_to_verdict(score)
    verdict = ClaimVerdict(verdict_str)
    confidence = score_to_confidence(score)

    return Claim(
        id="",
        text=claim_text,
        verdict=verdict,
        source_ids=[source_id] if source_id else [],
        confidence=confidence,
        rationale=(
            f"MiniCheck heuristic score={score:.2f}; "
            f"quote: {quote[:80]}..." if quote else f"MiniCheck heuristic score={score:.2f}"
        ),
    )


def _llm_verify(
    draft: DraftAnswer,
    contexts: List[RetrievedContext],
    query: str,
    extracted_ids: Dict[str, str],
) -> LLMVerificationOutput:
    model = get_chat_model(temperature=0.0).with_structured_output(LLMVerificationOutput)
    prompt = (
        f"{VERIFIER_PROMPT}\n\n"
        f"User question: {query}\n\n"
        f"SOURCES:\n{_sources_block(contexts)}\n\n"
        f"DRAFT:\n{draft.body}\n\n"
        "Verify each factual claim. Link every verdict to source_ids and supporting_quote. "
        "Mark contradicted if sources conflict. Mark unsupported if no source backs the claim."
    )
    return model.invoke(prompt)


def _apply_minicheck_refinement(claim: Claim, contexts: List[RetrievedContext]) -> Claim:
    """Re-score low-confidence LLM verdicts with heuristic MiniCheck."""
    settings = get_settings()
    if claim.confidence >= settings.confidence_threshold_medium + 2:
        return claim

    passages = [(c.id, c.snippet) for c in contexts]
    score, source_id, quote = batch_check(claim.text, passages)
    mc_verdict = ClaimVerdict(score_to_verdict(score))
    mc_conf = score_to_confidence(score)

    # If MiniCheck is stricter, tighten verdict
    if mc_conf < claim.confidence or mc_verdict in (
        ClaimVerdict.UNSUPPORTED,
        ClaimVerdict.CONTRADICTED,
    ):
        return claim.model_copy(
            update={
                "verdict": mc_verdict,
                "confidence": min(claim.confidence, mc_conf),
                "source_ids": claim.source_ids or ([source_id] if source_id else []),
                "rationale": claim.rationale + f" | MiniCheck adjusted (score={score:.2f}).",
            }
        )
    return claim


def verify_draft(
    draft: DraftAnswer,
    contexts: List[RetrievedContext],
    query: str = "",
) -> VerificationReport:
    """Produce a VerificationReport for the draft against sources."""
    if not draft.body.strip() or not contexts:
        return VerificationReport(
            claims=[],
            contradictions=[],
            recommended_edits=["No draft or sources to verify."],
            unsupported_critical_count=0,
        )

    if "do not have enough information" in draft.body.lower():
        return VerificationReport(
            claims=[],
            recommended_edits=[],
            unsupported_critical_count=0,
        )

    extracted = extract_claims(draft.body, query=query, contexts=contexts)
    id_map = {e.id: e.text for e in extracted}

    claims: List[Claim] = []
    contradictions: List[dict] = []
    recommended_edits: List[str] = []

    if is_llm_available():
        try:
            llm_out = _llm_verify(draft, contexts, query, id_map)
            for i, lv in enumerate(llm_out.claims):
                cid = lv.id if lv.id else f"claim-{i + 1}"
                claim = Claim(
                    id=cid,
                    text=lv.text or id_map.get(cid, lv.text),
                    verdict=lv.verdict,
                    source_ids=[s for s in lv.source_ids if s in _context_by_id(contexts)],
                    confidence=lv.confidence,
                    rationale=lv.rationale or f"Source quote: {lv.supporting_quote[:100]}",
                )
                claim = _apply_minicheck_refinement(claim, contexts)
                claims.append(claim)
            contradictions = llm_out.contradictions
            recommended_edits = llm_out.recommended_edits
        except Exception:
            claims = []

    if not claims:
        # Sentence-level heuristic verification (more stable for template drafts)
        from src.verification.refiner import _sentences
        from src.verification.claim_extractor import _should_skip_chunk

        for sent in _sentences(draft.body):
            if _should_skip_chunk(sent) or len(sent) < 20:
                continue
            c = _heuristic_verify_claim(sent, contexts)
            claims.append(c.model_copy(update={"id": f"claim-{len(claims) + 1}", "text": sent[:400]}))
        if not claims:
            for item in extracted:
                c = _heuristic_verify_claim(item.text, contexts)
                claims.append(c.model_copy(update={"id": item.id}))

    critical = sum(
        1
        for c in claims
        if c.verdict in (ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTED)
    )
    if critical and not recommended_edits:
        recommended_edits = [
            f"Remove or rewrite {critical} unsupported/contradicted claim(s).",
            "Re-cite sources for partial claims.",
        ]

    return VerificationReport(
        claims=claims,
        contradictions=contradictions,
        recommended_edits=recommended_edits,
        unsupported_critical_count=critical,
    )


def serialize_report(report: VerificationReport) -> dict:
    """JSON-serializable audit snapshot."""
    return report.model_dump(mode="json")
