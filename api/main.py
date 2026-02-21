"""
Agentic Stock Analyzer — FastAPI Backend
Serves the LangGraph agent via SSE streaming and provides stock data endpoints.
"""
import json
import os
import sys
import traceback
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Ensure root project dir is on sys.path so `app.graph` resolves
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# ── App Setup ──────────────────────────────────────────────
app = FastAPI(title="Agentic Stock Analyzer API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (vanilla HTML fallback)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ── LangGraph Initialization ──────────────────────────────
agent_graph = None
_graph_error: str | None = None

try:
    from app.graph import build_graph
    agent_graph = build_graph()
except Exception as exc:
    _graph_error = f"LangGraph init failed: {exc}\n{traceback.format_exc()}"
    print(f"⚠️  {_graph_error}")

# ── Models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


# ── Routes ─────────────────────────────────────────────────

@app.get("/")
def root():
    """Serve index.html if available, otherwise show API status."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "online", "graph_ready": agent_graph is not None}


@app.get("/api/health")
def health():
    """Health check endpoint for tests and monitoring."""
    return {
        "status": "healthy",
        "graph_ready": agent_graph is not None,
        "graph_error": _graph_error,
    }


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
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
            events = agent_graph.stream(
                {"messages": [("user", request.message)]},
                config=config,
                stream_mode="updates",
            )

            final_content = ""
            for event in events:
                for node_name, values in event.items():
                    # Emit agent_start
                    yield {
                        "event": "agent_start",
                        "data": json.dumps({"node": node_name}),
                    }

                    # Extract messages from agent output
                    if "messages" in values:
                        for msg in values["messages"]:
                            content = getattr(msg, "content", "")
                            if content:
                                final_content = content
                                yield {
                                    "event": "agent_output",
                                    "data": json.dumps({
                                        "node": node_name,
                                        "content": content,
                                    }),
                                }

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


@app.post("/api/chat")
async def chat_sync(request: ChatRequest):
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


@app.get("/api/stock/{ticker}")
async def get_stock_data(ticker: str, period: str = Query("6mo", pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|max)$")):
    """
    Fetch stock price data from yfinance for the chart and stats cards.
    Returns price history and key metrics.
    """
    try:
        import yfinance as yf

        stock = yf.Ticker(ticker.upper())
        info = stock.info or {}
        hist = stock.history(period=period)

        if hist.empty:
            return {"error": f"No data found for ticker '{ticker}'"}

        # Price history for charts
        price_data = []
        for date, row in hist.iterrows():
            price_data.append({
                "time": date.strftime("%Y-%m-%d"),
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })

        # Key stats
        current_price = price_data[-1]["close"] if price_data else 0
        prev_close = info.get("previousClose", price_data[-2]["close"] if len(price_data) > 1 else current_price)
        change = round(current_price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0

        return {
            "ticker": ticker.upper(),
            "name": info.get("shortName", ticker.upper()),
            "price": current_price,
            "change": change,
            "changePct": change_pct,
            "volume": price_data[-1]["volume"] if price_data else 0,
            "marketCap": info.get("marketCap"),
            "peRatio": info.get("trailingPE"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "history": price_data,
        }

    except Exception as exc:
        return {"error": str(exc), "ticker": ticker}


# ── Main ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
