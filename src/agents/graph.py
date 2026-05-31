"""LangGraph orchestrator — Phase 2: RAG + verify/refine loop."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Literal, Optional

from langgraph.graph import END, START, StateGraph

from src.agents.nodes import (
    draft_node,
    justify_node,
    planner_node,
    query_processor_node,
    refine_node,
    retrieve_node,
    verify_node,
)
from src.agents.state import AgentState
from src.config.settings import get_settings
from src.models.schemas import JustificationBundle


def _route_after_verify(state: AgentState) -> Literal["refine", "justify"]:
    settings = get_settings()
    unsupported = state.get("unsupported_critical_count") or 0
    iteration = state.get("iteration") or 0
    draft = state.get("draft")
    body = draft.body if draft and hasattr(draft, "body") else ""
    # Avoid infinite refine on already-collapsed answers
    if "do not have enough verified information" in body.lower():
        return "justify"
    if unsupported > 0 and iteration < settings.max_refine_iterations:
        return "refine"
    return "justify"


def build_graph(include_justify: bool = True, include_verify_loop: bool = True):
    """Build and compile the full pipeline."""
    workflow = StateGraph(AgentState)

    workflow.add_node("query_processor", query_processor_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("draft", draft_node)

    if include_verify_loop:
        workflow.add_node("verify", verify_node)
        workflow.add_node("refine", refine_node)

    if include_justify:
        workflow.add_node("justify", justify_node)

    workflow.add_edge(START, "query_processor")
    workflow.add_edge("query_processor", "planner")
    workflow.add_edge("planner", "retrieve")
    workflow.add_edge("retrieve", "draft")

    if include_verify_loop:
        workflow.add_edge("draft", "verify")
        workflow.add_conditional_edges(
            "verify",
            _route_after_verify,
            {"refine": "refine", "justify": "justify" if include_justify else END},
        )
        workflow.add_edge("refine", "verify")
        if include_justify:
            workflow.add_edge("justify", END)
        elif not include_justify:
            pass  # justify path handled in conditional
    elif include_justify:
        workflow.add_edge("draft", "justify")
        workflow.add_edge("justify", END)
    else:
        workflow.add_edge("draft", END)

    return workflow.compile()


def run_graph(
    query: str,
    stakes: str = "medium",
    include_justify: bool = True,
    include_verify_loop: bool = True,
) -> JustificationBundle:
    """Execute the graph and return the justification bundle."""
    graph = build_graph(
        include_justify=include_justify,
        include_verify_loop=include_verify_loop,
    )
    result = graph.invoke(
        {
            "query": query,
            "stakes": stakes,
            "iteration": 0,
            "unsupported_critical_count": 0,
        }
    )

    if include_justify:
        justification = result.get("justification")
        if justification is None:
            raise RuntimeError("Graph completed without a justification bundle.")
        if isinstance(justification, dict):
            return JustificationBundle.model_validate(justification)
        return justification

    draft = result.get("draft")
    contexts = result.get("contexts") or []
    report = result.get("verification_report")
    from src.models.schemas import Citation, ConfidenceBand

    citations = []
    if draft and draft.inline_citations:
        citations = list(draft.inline_citations)
    elif contexts:
        citations = [
            Citation(source_id=c.id, url=c.url, title=c.title, quoted_span=c.snippet[:80])
            for c in contexts
        ]

    return JustificationBundle(
        answer=draft.body if draft else "",
        claims=report.claims if report else [],
        citations=citations,
        phase="2-verify-draft-only",
        overall_confidence=ConfidenceBand.MEDIUM,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run NL ChatGPT Agentic RAG pipeline (Phase 2)."
    )
    parser.add_argument("--query", required=True, help="User question to process")
    parser.add_argument(
        "--stakes",
        default="medium",
        choices=["low", "medium", "high"],
        help="Stakes level for the query",
    )
    parser.add_argument(
        "--draft-only",
        action="store_true",
        help="Stop after draft (skip verify loop)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip verify/refine loop (Phase 1 behavior)",
    )
    args = parser.parse_args(argv)

    if args.draft_only:
        include_justify = False
        include_verify = False
    elif args.no_verify:
        include_justify = True
        include_verify = False
    else:
        include_justify = True
        include_verify = True

    bundle = run_graph(
        query=args.query,
        stakes=args.stakes,
        include_justify=include_justify,
        include_verify_loop=include_verify,
    )
    print(json.dumps(bundle.model_dump(mode="json"), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
