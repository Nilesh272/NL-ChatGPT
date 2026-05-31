"""Refine draft by removing or correcting unsupported claims."""

from __future__ import annotations

import re
from typing import List, Optional, Set

from src.llm.client import get_chat_model, is_llm_available
from src.models.schemas import Claim, ClaimVerdict, DraftAnswer, RetrievedContext, VerificationReport
from src.prompts.templates import MASTER_SYSTEM_PROMPT


def _sentences(body: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", body.strip())
    return [p.strip() for p in parts if p.strip()]


def _claim_matches_sentence(sentence: str, claim: Claim) -> bool:
    claim_words = set(re.findall(r"[a-z0-9]{4,}", claim.text.lower()))
    sent_words = set(re.findall(r"[a-z0-9]{4,}", sentence.lower()))
    if not claim_words:
        return claim.text.lower() in sentence.lower()
    overlap = claim_words & sent_words
    return len(overlap) >= max(2, len(claim_words) * 0.4)


def _heuristic_refine(
    body: str,
    report: VerificationReport,
    contexts: Optional[List[RetrievedContext]] = None,
) -> str:
    """Remove sentences tied to unsupported or contradicted claims."""
    bad_claims = [
        c
        for c in report.claims
        if c.verdict in (ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTED)
    ]
    if not bad_claims:
        return body

    sentences = _sentences(body)
    kept: List[str] = []
    removed: List[str] = []

    for sent in sentences:
        from src.verification.claim_extractor import _should_skip_chunk

        if _should_skip_chunk(sent):
            continue
        drop = any(_claim_matches_sentence(sent, bc) for bc in bad_claims)
        if drop and contexts and re.search(r"\[(src-|pplx-)\d+\]", sent):
            from src.verification.minicheck import batch_check
            from src.verification.verifier import _cited_passages

            passages = _cited_passages(sent, contexts)
            if passages:
                score, _, _ = batch_check(sent, passages)
                if score >= 0.35:
                    drop = False
        if drop:
            removed.append(sent[:80])
        else:
            kept.append(sent)

    if not kept:
        return (
            "After verification, the prior answer contained unsupported claims that were removed. "
            "I do not have enough verified information to provide a complete answer. "
            "Please see the justification panel for details."
        )

    # Avoid over-stripping: if refine removes most of the answer, keep the original draft.
    if len(kept) < max(1, len(sentences) // 3):
        return body

    result = " ".join(kept)
    if removed:
        note = (
            "\n\n_[Verification note: Removed unsupported statement(s) "
            f"after source check ({len(removed)} segment(s)).]_"
        )
        result = result + note
    return result


def _llm_refine(
    body: str,
    report: VerificationReport,
    query: str,
    sources_block: str,
) -> str:
    model = get_chat_model(temperature=0.1)
    bad = [
        f"- [{c.id}] {c.text} ({c.verdict.value}): {c.rationale}"
        for c in report.claims
        if c.verdict in (ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTED, ClaimVerdict.PARTIAL)
    ]
    prompt = (
        f"User question: {query}\n\n"
        f"SOURCES:\n{sources_block}\n\n"
        f"DRAFT:\n{body}\n\n"
        f"VERIFICATION ISSUES:\n" + "\n".join(bad) + "\n\n"
        "Rewrite the FULL answer to fix verification issues while staying complete (2–4 paragraphs). "
        "Remove unsupported claims entirely. Keep source-backed statements with [src-N] citations. "
        "Do not paste raw markdown from snippets. Do not introduce new facts."
    )
    response = model.invoke(
        [
            {"role": "system", "content": MASTER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )
    return response.content if hasattr(response, "content") else str(response)


def refine_draft(
    draft: DraftAnswer,
    report: VerificationReport,
    query: str = "",
    sources_block: str = "",
    contexts: Optional[List[RetrievedContext]] = None,
) -> DraftAnswer:
    """Return patched draft after verification."""
    if report.unsupported_critical_count == 0:
        return draft

    body = draft.body
    original_len = len(body)
    if is_llm_available() and sources_block:
        try:
            body = _llm_refine(body, report, query, sources_block)
        except Exception:
            body = _heuristic_refine(body, report, contexts)
    else:
        body = _heuristic_refine(body, report, contexts)

    # If refine collapsed the answer, keep the pre-refine draft (user sees gaps in panel).
    if len(body.strip()) < max(120, original_len // 4):
        body = draft.body

    # Strip citations to removed sources if needed — keep existing citations
    cited_ids: Set[str] = set(re.findall(r"\[(src-\d+|pplx-\d+)\]", body))
    citations = draft.inline_citations
    if cited_ids:
        citations = [c for c in citations if c.source_id in cited_ids] or citations

    return DraftAnswer(body=body, inline_citations=citations)
