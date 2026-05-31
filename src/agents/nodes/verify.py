"""Self-verification: compare draft claims to retrieved sources."""

from src.agents.state import AgentState
from src.models.schemas import DraftAnswer
from src.verification.verifier import serialize_report, verify_draft


def verify_node(state: AgentState) -> dict:
    draft = state.get("draft")
    contexts = state.get("contexts") or []
    query = state.get("query") or ""

    if not draft or not isinstance(draft, DraftAnswer):
        if isinstance(draft, dict):
            draft = DraftAnswer.model_validate(draft)
        else:
            draft = DraftAnswer(body="", inline_citations=[])

    report = verify_draft(draft, contexts, query=query)

    return {
        "verification_report": report,
        "unsupported_critical_count": report.unsupported_critical_count,
        "verification_snapshot": serialize_report(report),
    }
