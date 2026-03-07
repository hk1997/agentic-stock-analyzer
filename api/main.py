"""
Agentic Stock Analyzer — FastAPI Backend
Serves the LangGraph agent via SSE streaming and provides stock data endpoints.
"""
import json
import os
import sys
import time
import asyncio
import traceback
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.cache import get_cache, set_cache, cached_async, close_valkey_pool
from app.tasks import update_active_tickers_prices, log_user_query, trigger_jit_fundamentals, _ingest_price_history

from dotenv import load_dotenv
from fastapi import FastAPI, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Ensure root project dir is on sys.path so `app.graph` resolves
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if os.path.exists(os.path.join(PROJECT_ROOT, "local.env")):
    load_dotenv(os.path.join(PROJECT_ROOT, "local.env"))
else:
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# ── App Setup ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Kick off lightweight background data refresh for recently active tickers
    asyncio.create_task(update_active_tickers_prices())
    yield
    # Shutdown
    await close_valkey_pool()

app = FastAPI(title="Agentic Stock Analyzer API", version="0.2.0", lifespan=lifespan)

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
        if agent_graph is None:  # In this case agent_graph is actually the builder
            yield {"event": "error", "data": json.dumps({"message": _graph_error or "Agent graph not initialized"})}
            return

        config = {"configurable": {"thread_id": request.thread_id}}

        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool
            
            # Use the global DATABASE_URL from our env config
            db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/stock_analyzer")
            # langgraph-checkpoint-postgres requires psycopg connection string format
            psycopg_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
            
            async with AsyncConnectionPool(
                conninfo=psycopg_url,
                max_size=20,
                kwargs={"autocommit": True}
            ) as pool:
                checkpointer = AsyncPostgresSaver(pool)
                # First time setup, ensure tables exist
                await checkpointer.setup()
                
                # Compile per-request with the async checkpointer
                graph = agent_graph.compile(checkpointer=checkpointer)

                # We must use astream_events for token-by-token streaming
                events = graph.astream_events(
                    {"messages": [("user", request.message)]},
                    config=config,
                    version="v2"
                )

                current_node = None
                final_content = ""

                async for event in events:
                    kind = event["event"]
                    
                    # Detect which node is currently active (Supervisor or an Analyst)
                    if kind == "on_chain_start":
                        # LangGraph nodes are represented as chains
                        name = event.get("name")
                        if name in ["IntentClassifier", "TechnicalAnalyst", "SentimentAnalyst", "FundamentalAnalyst", "ValuationAnalyst", "QuantAnalyst"]:
                            current_node = name
                            yield {
                                "event": "agent_start",
                                "data": json.dumps({"node": current_node}),
                            }

                    # Stream tokens from the chat model
                    elif kind == "on_chat_model_stream":
                        if current_node:  # Only stream if we are inside a specific analyst node
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

                    # Node finished
                    elif kind == "on_chain_end":
                        name = event.get("name")
                        if name == current_node:
                            # Optional: Emit a complete signal for this node if needed
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


@app.post("/api/chat")
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


# ── Caching ────────────────────────────────────────────────
# Using Valkey via app.cache
CACHE_TTL = 300

@app.get("/api/stock/{ticker}")
async def get_stock_data(ticker: str, background_tasks: BackgroundTasks, period: str = Query("10d", pattern="^(1d|5d|10d|1mo|3mo|6mo|1y|2y|5y|max)$")):
    """
    Fetch stock price data from yfinance for the chart and stats cards.
    Returns price history and key metrics.
    """
    # Log user query asynchronously
    background_tasks.add_task(log_user_query, ticker, "chart")
    
    cache_key = f"api:stock:{ticker.upper()}:{period}"
    cached_data = await get_cache(cache_key)
    if cached_data is not None:
        return cached_data

    try:
        import yfinance as yf
        import concurrent.futures

        yf_period = "1mo" if period == "10d" else period

        def fetch_info():
            return yf.Ticker(ticker.upper()).info or {}

        def fetch_history():
            return yf.Ticker(ticker.upper()).history(period=yf_period)

        # Use a dedicated ThreadPoolExecutor for yfinance to prevent blocking the main asyncio default pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="yf_worker") as yf_executor:
            loop = asyncio.get_running_loop()
            info, hist = await asyncio.gather(
                loop.run_in_executor(yf_executor, fetch_info),
                loop.run_in_executor(yf_executor, fetch_history)
            )

        if hist.empty:
            return {"error": f"No data found for ticker '{ticker}'"}
            
        # JIT: Trigger an async upsert into TimescaleDB so we have this historical data natively
        # We don't await this directly in the main thread to avoid delaying the UI response,
        # but we add it to the background tasks to ensure it happens.
        background_tasks.add_task(_ingest_price_history, ticker)
            
        if period == "10d" and len(hist) > 10:
            hist = hist.tail(10)

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

        result = {
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
        
        
        await set_cache(cache_key, result, CACHE_TTL)
        return result

    except Exception as exc:
        return {"error": str(exc), "ticker": ticker}

@app.get("/api/indicators/{ticker}")
@cached_async(ttl_seconds=300)
async def get_stock_indicators(ticker: str, background_tasks: BackgroundTasks, period: str = Query("1y", pattern="^(1mo|3mo|6mo|1y|2y|5y|max)$")):
    """
    Calculates technical indicators for the frontend charts.
    """
    # Log user query asynchronously
    background_tasks.add_task(log_user_query, ticker, "indicators")
    
    try:
        import yfinance as yf
        import pandas as pd
        import concurrent.futures

        def fetch_history():
            return yf.Ticker(ticker.upper()).history(period=period)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5, thread_name_prefix="yf_ind_worker") as executor:
            loop = asyncio.get_running_loop()
            hist = await loop.run_in_executor(executor, fetch_history)

        if hist.empty:
            return {"error": f"No data found for ticker '{ticker}'"}

        # Calculate indicators
        close = hist["Close"]
        
        # SMAs
        sma20 = close.rolling(window=20).mean()
        sma50 = close.rolling(window=50).mean()
        sma200 = close.rolling(window=200).mean()
        
        # EMAs
        ema20 = close.ewm(span=20, adjust=False).mean()
        
        # Bollinger Bands (20-day, 2 std dev, population std dev ddof=0 to match industry standard)
        std20 = close.rolling(window=20).std(ddof=0)
        upper_band = sma20 + (std20 * 2)
        lower_band = sma20 - (std20 * 2)
        
        # RSI (14-day) - Using Wilder's Smoothing Method
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Wilder's Smoothing: EMA with alpha = 1 / window
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # MACD (12, 26, 9)
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal

        # Prepare payload
        indicators_data = []
        for date in hist.index:
            indicators_data.append({
                "time": date.strftime("%Y-%m-%d"),
                "sma20": round(sma20.loc[date], 2) if not pd.isna(sma20.loc[date]) else None,
                "sma50": round(sma50.loc[date], 2) if not pd.isna(sma50.loc[date]) else None,
                "sma200": round(sma200.loc[date], 2) if not pd.isna(sma200.loc[date]) else None,
                "ema20": round(ema20.loc[date], 2) if not pd.isna(ema20.loc[date]) else None,
                "upper_band": round(upper_band.loc[date], 2) if not pd.isna(upper_band.loc[date]) else None,
                "lower_band": round(lower_band.loc[date], 2) if not pd.isna(lower_band.loc[date]) else None,
                "rsi": round(rsi.loc[date], 2) if not pd.isna(rsi.loc[date]) else None,
                "macd": round(macd.loc[date], 2) if not pd.isna(macd.loc[date]) else None,
                "macd_signal": round(signal.loc[date], 2) if not pd.isna(signal.loc[date]) else None,
                "macd_hist": round(histogram.loc[date], 2) if not pd.isna(histogram.loc[date]) else None,
            })

        return {"ticker": ticker.upper(), "indicators": indicators_data}

    except Exception as exc:
        return {"error": str(exc), "ticker": ticker}

class BacktestRequestAPI(BaseModel):
    ticker: str
    strategy: str = "sma_crossover"
    initial_capital: float = 10000.0
    days: int = 365

@app.post("/api/backtest")
@cached_async(ttl_seconds=3600) # Longer TTL for backtesting results
async def run_backtest(request: BacktestRequestAPI):
    """
    Runs a strategy backtest and returns JSON results.
    """
    try:
        from app.tools import backtest_strategy
        import concurrent.futures
        import json

        def _run():
            return backtest_strategy.invoke({
                "ticker": request.ticker,
                "strategy": request.strategy,
                "initial_capital": request.initial_capital,
                "days": request.days
            })
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="bt_worker") as executor:
            loop = asyncio.get_running_loop()
            result_str = await loop.run_in_executor(executor, _run)
            
        if isinstance(result_str, str):
            try:
                return json.loads(result_str)
            except json.JSONDecodeError:
                return {"error": result_str}
        return result_str
        
    except Exception as exc:
        return {"error": str(exc)}

# ── Fundamentals Narrative Endpoints ───────────────────────

@app.get("/api/fundamentals/{ticker}/story")
@cached_async(ttl_seconds=2592000) # 30 Days TTL
async def get_fundamental_story(ticker: str, background_tasks: BackgroundTasks):
    """Generates the Business Model Story via Gemini."""
    
    # Just-In-Time Generation fallback: While the user reads the story, trigger Porter/Competitor generation in bg.
    background_tasks.add_task(trigger_jit_fundamentals, ticker)
    background_tasks.add_task(log_user_query, ticker, "fundamentals")
    
    try:
        from app.fundamentals import generate_business_story
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            loop = asyncio.get_running_loop()
            markdown_result = await loop.run_in_executor(executor, generate_business_story, ticker)
            
        return {"ticker": ticker.upper(), "markdown": markdown_result}
    except Exception as exc:
        return {"error": str(exc)}

@app.get("/api/fundamentals/{ticker}/porter")
@cached_async(ttl_seconds=2592000) # 30 Days TTL
async def get_fundamental_porter(ticker: str):
    """Generates Porter's 5 Forces Analysis via Gemini."""
    try:
        from app.fundamentals import generate_porter_forces
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            loop = asyncio.get_running_loop()
            markdown_result = await loop.run_in_executor(executor, generate_porter_forces, ticker)
            
        return {"ticker": ticker.upper(), "markdown": markdown_result}
    except Exception as exc:
        return {"error": str(exc)}

@app.get("/api/fundamentals/{ticker}/competitors")
@cached_async(ttl_seconds=2592000) # 30 Days TTL
async def get_fundamental_competitors(ticker: str):
    """Generates Top 3 Competitor Comparison via Gemini."""
    try:
        from app.fundamentals import generate_competitor_comparison
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            loop = asyncio.get_running_loop()
            markdown_result = await loop.run_in_executor(executor, generate_competitor_comparison, ticker)
            
        return {"ticker": ticker.upper(), "markdown": markdown_result}
    except Exception as exc:
        return {"error": str(exc)}

# ── News & Sentiment Endpoints ─────────────────────────────────

@app.get("/api/news/{ticker}")
@cached_async(ttl_seconds=3600) # 1 hour TTL
async def get_recent_news(ticker: str):
    """Fetches recent news articles for the ticker using DuckDuckGo search."""
    try:
        from ddgs import DDGS
        import concurrent.futures
        
        def _fetch_news():
            ddgs = DDGS()
            results = ddgs.news(f"{ticker} stock news", max_results=10)
            # Format to match the expected duckduckgo raw string output from the UI
            # which expects `[snippet: ..., title: ..., link: ...]`
            formatted_string = ""
            for item in results:
                formatted_string += f"[snippet: {item.get('body', '')}, title: {item.get('title', '')}, link: {item.get('url', '')}], "
            return formatted_string
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            loop = asyncio.get_running_loop()
            news_str = await loop.run_in_executor(executor, _fetch_news)
            
        return {"ticker": ticker.upper(), "news_raw": news_str}
    except Exception as exc:
        return {"error": str(exc)}

@app.get("/api/news/{ticker}/sentiment")
@cached_async(ttl_seconds=3600) # 1 hour TTL
async def get_news_sentiment(ticker: str):
    """Fetches recent news and generates an AI sentiment summary."""
    try:
        from app.llm import get_llm
        from langchain_core.messages import HumanMessage
        from ddgs import DDGS
        import concurrent.futures
        
        def _generate_sentiment():
            ddgs = DDGS()
            results = ddgs.news(f"{ticker} stock news", max_results=10)
            if not results:
                return "Failed to retrieve recent news for sentiment analysis."
                
            formatted_news = ""
            for item in results:
                formatted_news += f"- {item.get('title', '')}: {item.get('body', '')}\n"
                
            llm = get_llm(temperature=0.3)
            prompt = (
                f"You are an expert financial sentiment analyst. Read the following recent news snippets for {ticker} "
                f"and provide a concise, 2-3 sentence summary of the overarching market sentiment (bullish, bearish, or neutral) "
                f"and the primary catalysts driving it.\n\nNews Data:\n{formatted_news}\n\nSentiment Summary:"
            )
            response = llm.invoke([HumanMessage(content=prompt)])
            return response.content
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            loop = asyncio.get_running_loop()
            sentiment_summary = await loop.run_in_executor(executor, _generate_sentiment)
            
        return {"ticker": ticker.upper(), "sentiment_summary": sentiment_summary}
    except Exception as exc:
        return {"error": str(exc)}

# ── SEC Filings Endpoints ─────────────────────────────────────

@app.get("/api/filings/{ticker}")
@cached_async(ttl_seconds=86400) # 1 day TTL
async def get_recent_filings(ticker: str):
    """Fetches recent SEC filings metadata."""
    try:
        from app.filings import get_recent_filings_metadata
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            loop = asyncio.get_running_loop()
            filings_meta = await loop.run_in_executor(executor, get_recent_filings_metadata, ticker, 10)
            
        return {"ticker": ticker.upper(), "filings": filings_meta}
    except Exception as exc:
        return {"error": str(exc)}

@app.get("/api/filings/{ticker}/mda")
@cached_async(ttl_seconds=604800) # 7 days TTL
async def get_filings_mda(ticker: str):
    """Extracts and summarizes MD&A from the latest 10-K."""
    try:
        from app.filings import generate_mda_summary
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            loop = asyncio.get_running_loop()
            mda_summary = await loop.run_in_executor(executor, generate_mda_summary, ticker)
            
        return {"ticker": ticker.upper(), "markdown": mda_summary}
    except Exception as exc:
        return {"error": str(exc)}

@app.get("/api/filings/{ticker}/risks")
@cached_async(ttl_seconds=604800) # 7 days TTL
async def get_filings_risks(ticker: str):
    """Extracts and summarizes Risk Factors from the latest 10-K."""
    try:
        from app.filings import generate_risk_summary
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            loop = asyncio.get_running_loop()
            risk_summary = await loop.run_in_executor(executor, generate_risk_summary, ticker)
            
        return {"ticker": ticker.upper(), "markdown": risk_summary}
    except Exception as exc:
        return {"error": str(exc)}

# ── Main ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
