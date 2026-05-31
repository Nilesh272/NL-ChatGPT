"""Streamlit widgets for Phase 5 human judgment."""

from __future__ import annotations

import uuid
from typing import Optional

import streamlit as st

from src.models.judgment import UserClaimVerdict
from src.models.schemas import Claim, JustificationBundle
from src.storage.judgment_store import JudgmentStore
from src.ui.confidence import claim_confidence_style
from src.ui.judgment import (
    FELLOWSHIP_PILLARS,
    VERDICT_LABELS,
    build_export_json,
    build_export_markdown,
    build_export_payload,
    can_copy_or_export,
    stakes_requires_signoff,
)
VERDICT_OPTIONS = ["Trust", "Unsure", "Reject"]
VERDICT_MAP = {
    "Trust": UserClaimVerdict.TRUST,
    "Unsure": UserClaimVerdict.UNSURE,
    "Reject": UserClaimVerdict.REJECT,
}


def ensure_session_ids() -> tuple[str, str]:
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    return st.session_state.session_id, st.session_state.session_id


def new_turn_id() -> str:
    return str(uuid.uuid4())


def _claim_css_class(confidence: int, verdict: str) -> str:
    from src.config.settings import get_settings

    if verdict in ("unsupported", "contradicted"):
        return "claim-weak"
    settings = get_settings()
    if confidence >= settings.confidence_threshold_high:
        return "claim-supported"
    if confidence >= settings.confidence_threshold_medium:
        return "claim-partial"
    return "claim-weak"


def render_claim_with_judgment(
    claim: Claim,
    session_id: str,
    turn_id: str,
    stakes: str,
    query: str,
    store: JudgmentStore,
    key_suffix: str,
) -> None:
    """Per-claim Trust / Unsure / Reject + note."""
    existing = store.get_turn_reviews(session_id, turn_id)
    by_id = {r.claim_id: r for r in existing.claim_reviews}
    prior = by_id.get(claim.id)

    label, color = claim_confidence_style(claim.confidence)
    css = _claim_css_class(claim.confidence, claim.verdict.value)
    sources = ", ".join(claim.source_ids) if claim.source_ids else "—"

    st.markdown(
        f'<div class="{css}">'
        f"<strong>{claim.id}</strong> · AI verdict: {claim.verdict.value} · "
        f'<span style="color:{color}">Confidence {claim.confidence}/10 ({label})</span><br/>'
        f"{claim.text}<br/>"
        f"<small>Sources: {sources}</small>"
        f"</div>",
        unsafe_allow_html=True,
    )

    default_verdict = VERDICT_LABELS.get(prior.verdict, "Trust") if prior else "Trust"
    idx = VERDICT_OPTIONS.index(default_verdict) if default_verdict in VERDICT_OPTIONS else 0

    c1, c2 = st.columns([2, 1])
    with c1:
        choice = st.radio(
            "Your judgment",
            VERDICT_OPTIONS,
            index=idx,
            horizontal=True,
            key=f"judgment_{key_suffix}_{claim.id}",
            help="You decide — the AI only assists evaluation.",
        )
    with c2:
        if prior:
            st.caption(f"Saved: **{prior.verdict.value}**")

    note = st.text_input(
        "Note (optional)",
        value=prior.note if prior else "",
        key=f"note_{key_suffix}_{claim.id}",
        placeholder="Why you trust, doubt, or reject this claim",
    )

    if st.button("Save review", key=f"save_{key_suffix}_{claim.id}", type="primary"):
        store.upsert_claim_review(
            session_id=session_id,
            turn_id=turn_id,
            claim_id=claim.id,
            verdict=VERDICT_MAP[choice],
            note=note,
            stakes=stakes,
            query=query,
        )
        st.success(f"Saved **{choice}** for {claim.id}")


def render_export_and_copy(
    bundle: JustificationBundle,
    turn_id: str,
    session_id: str,
    stakes: str,
    query: str,
    store: JudgmentStore,
    key_suffix: str,
) -> None:
    """Export + copy with high-stakes gates."""
    turn_review = store.get_turn_reviews(session_id, turn_id)
    allowed, block_reason = can_copy_or_export(stakes, turn_review)

    st.markdown("#### Export & copy")

    if stakes_requires_signoff(stakes):
        statement = (
            "I reviewed the sources and claims above and take responsibility "
            "for any decision based on this AI-assisted answer."
        )
        signed = st.checkbox(
            statement,
            value=turn_review.export_signed_off,
            key=f"signoff_{key_suffix}",
        )
        if signed != turn_review.export_signed_off:
            store.set_signoff(session_id, turn_id, signed, statement)

    if not allowed:
        st.warning(block_reason)
    else:
        st.caption("Copy/export unlocked after your review.")

    payload = build_export_payload(bundle, store.get_turn_reviews(session_id, turn_id), query)
    md = build_export_markdown(payload)
    js = build_export_json(payload)

    st.download_button(
        "Download review package (Markdown)",
        data=md,
        file_name=f"nl-chatgpt-review-{turn_id[:8]}.md",
        mime="text/markdown",
        disabled=not allowed,
        key=f"dl_md_{key_suffix}",
    )
    st.download_button(
        "Download review package (JSON)",
        data=js,
        file_name=f"nl-chatgpt-review-{turn_id[:8]}.json",
        mime="application/json",
        disabled=not allowed,
        key=f"dl_json_{key_suffix}",
    )

    if allowed:
        st.code(bundle.answer[:2000] + ("…" if len(bundle.answer) > 2000 else ""), language=None)
        st.caption("Use download buttons for full answer + justification + your verdicts.")


def render_session_rejections(session_id: str, store: JudgmentStore) -> None:
    rejected = store.list_rejected_for_session(session_id)
    if not rejected:
        return
    with st.expander(f"Claims you rejected this session ({len(rejected)})", expanded=False):
        for r in rejected:
            st.markdown(
                f"- **{r['claim_id']}** (turn `{r['turn_id'][:8]}…`): {r.get('note') or '_no note_'}"
            )


def render_fellowship_sidebar() -> None:
    with st.sidebar.expander("How this supports your judgment", expanded=False):
        st.markdown(FELLOWSHIP_PILLARS)
