"""
NL ChatGPT — Streamlit prototype (Phase 5: human judgment layer).

Run: streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm.client import get_llm_provider_label, is_llm_available
from src.models.schemas import ConfidenceBand, JustificationBundle
from src.retrieval.service import is_retrieval_available
from src.storage.judgment_store import get_judgment_store
from src.ui.confidence import review_banner
from src.ui.judgment import stakes_requires_claim_review
from src.ui.judgment_panel import (
    ensure_session_ids,
    new_turn_id,
    render_claim_with_judgment,
    render_export_and_copy,
    render_fellowship_sidebar,
    render_session_rejections,
)
from src.ui.runner import PipelineResult, run_pipeline, step_label

st.set_page_config(
    page_title="NL ChatGPT",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_plan" not in st.session_state:
    st.session_state.show_plan = False
if "expand_panel" not in st.session_state:
    st.session_state.expand_panel = False
def _init_css():
    st.markdown(
        """
        <style>
        .claim-supported { border-left: 4px solid #1b7f4e; padding-left: 10px; margin: 8px 0; }
        .claim-partial { border-left: 4px solid #b8860b; padding-left: 10px; margin: 8px 0; }
        .claim-weak { border-left: 4px solid #c0392b; padding-left: 10px; margin: 8px 0; }
        .banner-low { background: #fdecea; border: 1px solid #c0392b; padding: 12px; border-radius: 8px; }
        .banner-medium { background: #fff8e6; border: 1px solid #b8860b; padding: 12px; border-radius: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_confidence_banner(bundle: JustificationBundle):
    msg = review_banner(bundle.overall_confidence)
    if not msg:
        return
    css = "banner-low" if bundle.overall_confidence == ConfidenceBand.LOW else "banner-medium"
    st.markdown(f'<div class="{css}">{msg}</div>', unsafe_allow_html=True)


def _render_sources(bundle: JustificationBundle):
    if not bundle.citations:
        st.caption("No citations available.")
        return
    for cite in bundle.citations:
        st.markdown(f"**[{cite.source_id}]** [{cite.title}]({cite.url})")
        if cite.quoted_span:
            st.caption(cite.quoted_span)


def _render_justification_panel(
    bundle: JustificationBundle,
    result: PipelineResult,
    turn_id: str,
    session_id: str,
    stakes: str,
    query: str,
    expanded: bool,
    key_suffix: str,
):
    store = get_judgment_store()

    with st.container(border=True):
        st.markdown("### Justification & your review")
        st.caption(
            f"Overall confidence: **{bundle.overall_confidence.value.upper()}** · "
            "AI assists — **you** judge each claim."
        )
        _render_confidence_banner(bundle)

        if stakes_requires_claim_review(stakes):
            st.info(
                "**High stakes:** Review at least one claim and sign off before export."
            )
        elif stakes == "medium":
            st.caption("Medium stakes: claim review recommended before acting on the answer.")
        else:
            st.caption("Low stakes: light review — export is not gated.")

        if st.session_state.show_plan and bundle.verification_plan:
            with st.expander("Verification plan", expanded=expanded):
                for step in bundle.verification_plan:
                    st.markdown(f"- {step}")

        with st.expander("Sources", expanded=expanded):
            _render_sources(bundle)

        st.markdown("#### Claims — your judgment")
        if not bundle.claims:
            st.caption("No claims to review (answer may be a refusal or summary).")
        for claim in bundle.claims:
            render_claim_with_judgment(
                claim, session_id, turn_id, stakes, query, store, key_suffix
            )

        with st.expander("Assumptions & gaps", expanded=False):
            if bundle.assumptions:
                st.markdown("**Assumptions**")
                for a in bundle.assumptions:
                    st.markdown(f"- {a}")
            if bundle.gaps:
                st.markdown("**Gaps**")
                for g in bundle.gaps:
                    st.markdown(f"- {g}")

        with st.expander("Verify checklist", expanded=False):
            for i, item in enumerate(bundle.verify_checklist):
                st.checkbox(item, value=False, key=f"chk_{key_suffix}_{i}")

        render_export_and_copy(
            bundle, turn_id, session_id, stakes, query, store, key_suffix
        )


def _already_answered(query: str) -> bool:
    """Prevent double pipeline run if Streamlit replays the same chat_input."""
    messages = st.session_state.messages
    if len(messages) < 2:
        return False
    last = messages[-1]
    prev = messages[-2]
    return (
        last.get("role") == "assistant"
        and prev.get("role") == "user"
        and prev.get("content") == query
    )


def _render_sidebar():
    st.sidebar.title("Settings")
    stakes = st.sidebar.selectbox(
        "Stakes level",
        options=["low", "medium", "high"],
        index=2,
        help="High = claim review + sign-off required before export.",
    )
    st.session_state.show_plan = st.sidebar.checkbox(
        "Show verification plan",
        value=st.session_state.show_plan,
    )
    st.session_state.expand_panel = st.sidebar.checkbox(
        "Expand justification details",
        value=st.session_state.expand_panel,
    )
    include_verify = st.sidebar.checkbox("Enable verify/refine loop", value=True)

    st.sidebar.divider()
    st.sidebar.markdown("**API status**")
    if is_llm_available():
        st.sidebar.write(f"LLM: ✅ ({get_llm_provider_label()})")
    else:
        st.sidebar.write("LLM: ⚠️ mock — set GROQ_API_KEY or OPENAI_API_KEY")
    st.sidebar.write(f"Retrieval: {'✅' if is_retrieval_available() else '⚠️ mock'}")

    session_id, _ = ensure_session_ids()
    render_session_rejections(session_id, get_judgment_store())
    render_fellowship_sidebar()

    if st.sidebar.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()

    return stakes, include_verify


def _render_message(msg: dict, idx: int, session_id: str, default_stakes: str):
    """Render one turn from history (single source of truth — no duplicate columns)."""
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] != "assistant" or not msg.get("justification"):
            return

        bundle = msg["justification"]
        if isinstance(bundle, dict):
            bundle = JustificationBundle.model_validate(bundle)
        turn_id = msg.get("turn_id", f"hist_{idx}")
        _render_confidence_banner(bundle)

        with st.expander("Justification & review", expanded=False):
            _render_justification_panel(
                    bundle,
                    msg.get("pipeline") or PipelineResult(query="", stakes=default_stakes),
                    turn_id=turn_id,
                    session_id=session_id,
                    stakes=msg.get("stakes", default_stakes),
                    query=msg.get("user_query", ""),
                    expanded=st.session_state.expand_panel,
                    key_suffix=f"hist_{idx}",
            )


def main():
    _init_css()
    session_id, _ = ensure_session_ids()

    st.title("NL ChatGPT")
    st.caption(
        "Verified answers with citations — you stay in control via per-claim judgment."
    )

    stakes, include_verify = _render_sidebar()

    # --- Render full chat history only (avoids duplicate with live column layout) ---
    for idx, msg in enumerate(st.session_state.messages):
        _render_message(msg, idx, session_id, stakes)

    query = st.chat_input("Ask a question…")
    if not query or _already_answered(query):
        _render_consent_footer()
        return

    turn_id = new_turn_id()

    # Run pipeline once, then save to history and rerun.
    # Rendering live + appending caused the answer to appear twice on the next Streamlit rerun.
    with st.status("Running agent pipeline…", expanded=True) as status:

        def on_step(node: str, _update: dict):
            status.write(f"✓ {step_label(node)}")

        try:
            result = run_pipeline(
                query=query,
                stakes=stakes,
                on_step=on_step,
                include_verify_loop=include_verify,
            )
        except Exception as exc:
            status.update(label="Failed", state="error")
            st.error(f"Pipeline error: {exc}")
            _render_consent_footer()
            return

        if not result.ok:
            status.update(label="Failed", state="error")
            st.error(result.error or "Pipeline failed.")
            _render_consent_footer()
            return

        status.update(label="Complete", state="complete")

    bundle = result.justification
    st.session_state.messages.append({"role": "user", "content": query})
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": bundle.answer,
            "justification": bundle,
            "pipeline": result,
            "turn_id": turn_id,
            "stakes": stakes,
            "user_query": query,
        }
    )
    st.rerun()


def _render_consent_footer():
    st.divider()
    st.caption(
        "**Privacy & consent:** Queries may be sent to configured LLM and retrieval providers "
        "(Groq/OpenAI, Tavily). Judgment reviews are stored locally in `data/judgments.db` on this "
        "machine. Do not paste passwords, medical, or other sensitive PII. "
        "AI assists your judgment — you are responsible for final decisions."
    )


if __name__ == "__main__":
    main()
