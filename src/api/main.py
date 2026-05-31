"""
Optional FastAPI + SSE endpoint for the agent pipeline (Phase 3).

Run: uvicorn src.api.main:app --reload --port 8000
"""

from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal

from pydantic import BaseModel, Field

from src.ui.runner import run_pipeline, step_label

app = FastAPI(title="NL ChatGPT API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    stakes: Literal["low", "medium", "high"] = "medium"


@app.get("/health")
def health():
    return {"status": "ok", "phase": "3-ui"}


@app.post("/chat")
def chat_sync(body: ChatRequest):
    """Synchronous chat — returns full justification JSON."""
    result = run_pipeline(query=body.query, stakes=body.stakes)
    if not result.ok:
        raise HTTPException(status_code=500, detail=result.error or "Pipeline failed")
    return result.justification.model_dump(mode="json")


@app.get("/chat/stream")
async def chat_stream(query: str, stakes: str = "medium"):
    """
    Server-Sent Events stream of pipeline steps and final justification.
    Events: plan | sources | verification | justification | error
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        events = []

        def on_step(node: str, update: dict):
            payload = {"node": node, "label": step_label(node)}
            if node == "planner" and update.get("verification_plan"):
                plan = update["verification_plan"]
                plan_dict = plan.model_dump() if hasattr(plan, "model_dump") else plan
                events.append(("plan", plan_dict))
            elif node == "retrieve" and update.get("contexts"):
                ctxs = update["contexts"]
                sources = [
                    c.model_dump() if hasattr(c, "model_dump") else c for c in ctxs
                ]
                events.append(("sources", {"count": len(sources), "items": sources}))
            elif node == "verify" and update.get("verification_report"):
                rep = update["verification_report"]
                events.append(
                    (
                        "verification",
                        rep.model_dump() if hasattr(rep, "model_dump") else rep,
                    )
                )

        result = run_pipeline(query=query, stakes=stakes, on_step=on_step)

        for event_type, data in events:
            yield _sse(event_type, data)

        if result.error:
            yield _sse("error", {"message": result.error})
        elif result.justification:
            yield _sse("justification", result.justification.model_dump(mode="json"))
        else:
            yield _sse("error", {"message": "No justification produced"})

    from fastapi.responses import StreamingResponse

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
