import json
import os
import traceback
from typing import AsyncGenerator
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.graph import build_graph

# ── LangGraph Initialization ──────────────────────────────
agent_graph = None
_graph_error: str | None = None

try:
    agent_graph = build_graph()
except Exception as exc:
    _graph_error = f"LangGraph init failed: {exc}\n{traceback.format_exc()}"
    print(f"⚠️  {_graph_error}")

router = APIRouter(prefix="/api", tags=["agent"])

# ── Models ─────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"

# ── Routes ─────────────────────────────────────────────────
@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Stream LangGraph agent events via Server-Sent Events (SSE).

    Event types:
      - agent_start:  { node: "FundamentalAnalyst" }
      - agent_output: { node: "...", content: "..." }
      - error:        { message: "..." }
      - finish:       { summary: "..." }
    """

    async def event_generator() -> AsyncGenerator[dict, None]:
        if agent_graph is None:
            yield {"event": "error", "data": json.dumps({"message": _graph_error or "Agent graph not initialized"})}
            return

        config = {"configurable": {"thread_id": request.thread_id}}

        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool
            
            db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/stock_analyzer")
            psycopg_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
            
            async with AsyncConnectionPool(
                conninfo=psycopg_url,
                max_size=20,
                kwargs={"autocommit": True}
            ) as pool:
                checkpointer = AsyncPostgresSaver(pool)
                await checkpointer.setup()
                
                graph = agent_graph.compile(checkpointer=checkpointer)

                events = graph.astream_events(
                    {"messages": [("user", request.message)]},
                    config=config,
                    version="v2"
                )

                current_node = None
                final_content = ""

                async for event in events:
                    kind = event["event"]
                    
                    if kind == "on_chain_start":
                        name = event.get("name")
                        if name in ["IntentClassifier", "TechnicalAnalyst", "SentimentAnalyst", "FundamentalAnalyst", "ValuationAnalyst", "QuantAnalyst"]:
                            current_node = name
                            yield {
                                "event": "agent_start",
                                "data": json.dumps({"node": current_node}),
                            }

                    elif kind == "on_chat_model_stream":
                        if current_node:
                            chunk = event["data"]["chunk"]
                            if hasattr(chunk, "content") and chunk.content:
                                content_piece = chunk.content
                                if isinstance(content_piece, str):
                                    final_content += content_piece
                                    yield {
                                        "event": "agent_output_chunk",
                                        "data": json.dumps({
                                            "node": current_node,
                                            "content": content_piece,
                                        }),
                                    }

                    elif kind == "on_chain_end":
                        name = event.get("name")
                        if name == current_node:
                            current_node = None

                yield {
                    "event": "finish",
                    "data": json.dumps({"summary": final_content[:200] if final_content else "No response generated"}),
                }

        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"message": str(exc)}),
            }

    return EventSourceResponse(event_generator())


@router.post("/chat")
async def chat_sync(request: ChatRequest, background_tasks: BackgroundTasks):
    """Synchronous fallback: returns a single JSON response (for simple testing)."""
    if agent_graph is None:
        return {"reply": f"Error: {_graph_error}", "thread_id": request.thread_id}

    config = {"configurable": {"thread_id": request.thread_id}}
    final_response = ""

    events = agent_graph.stream(
        {"messages": [("user", request.message)]},
        config=config,
        stream_mode="updates",
    )

    for event in events:
        for node_name, values in event.items():
            if "messages" in values:
                for msg in values["messages"]:
                    if hasattr(msg, "content") and msg.content:
                        final_response = msg.content

    return {"reply": final_response, "thread_id": request.thread_id}
