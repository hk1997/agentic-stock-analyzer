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
from fastapi import FastAPI, Query, BackgroundTasks, UploadFile, File
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
    strategies: list[str] = ["sma_crossover"]
    initial_capital: float = 10000.0
    days: int = 365
    stop_loss_pct: float = 0.0

@app.post("/api/backtest")
@cached_async(ttl_seconds=3600) # Longer TTL for backtesting results
async def run_backtest(request: BacktestRequestAPI):
    """
    Runs a list of strategy backtests concurrently and returns JSON results.
    """
    try:
        from app.tools import backtest_strategy
        import concurrent.futures
        import json

        def _run(strategy_name: str):
            res = backtest_strategy.invoke({
                "ticker": request.ticker,
                "strategy": strategy_name,
                "initial_capital": request.initial_capital,
                "days": request.days,
                "stop_loss_pct": request.stop_loss_pct
            })
            if isinstance(res, str):
                try:
                    return json.loads(res)
                except json.JSONDecodeError:
                    return {"error": res, "strategy": strategy_name}
            return res
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=5, thread_name_prefix="bt_worker") as executor:
            loop = asyncio.get_running_loop()
            tasks = [
                loop.run_in_executor(executor, _run, strat)
                for strat in request.strategies
            ]
            results = await asyncio.gather(*tasks)
            
        return results
        
    except Exception as exc:
        return {"error": str(exc)}

@app.get("/api/levels/{ticker}")
@cached_async(ttl_seconds=3600)
async def get_key_levels(ticker: str):
    """Fetches key Support and Resistance levels for a ticker."""
    try:
        from app.tools import calculate_key_levels
        import concurrent.futures
        import json
        
        def _run():
            res = calculate_key_levels.invoke({"ticker": ticker})
            if isinstance(res, str):
                try:
                    return json.loads(res)
                except json.JSONDecodeError:
                    return {"error": res}
            return res

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(executor, _run)
            
        return result
    except Exception as exc:
        return {"error": str(exc)}

# ── Fundamentals Narrative Endpoints ───────────────────────

@app.get("/api/fundamentals/{ticker}/story")
@cached_async(ttl_seconds=86400) # Secondary cache to reduce DB queries
async def get_fundamental_story(ticker: str, background_tasks: BackgroundTasks):
    """Generates the Business Model Story via Gemini and permanently stores it in PostgreSQL."""
    background_tasks.add_task(trigger_jit_fundamentals, ticker)
    background_tasks.add_task(log_user_query, ticker, "fundamentals")
    
    ticker_upper = ticker.upper()
    from app.database import async_session
    from app.models import AIFundamentals
    from sqlalchemy import select
    
    async with async_session() as session:
        result = await session.execute(select(AIFundamentals).where(AIFundamentals.ticker == ticker_upper))
        db_record = result.scalar_one_or_none()
        if db_record and db_record.story:
            return {"ticker": ticker_upper, "markdown": db_record.story}
            
    try:
        from app.fundamentals import generate_business_story
        
        markdown_result = await generate_business_story(ticker)
        
        async with async_session() as session:
            result = await session.execute(select(AIFundamentals).where(AIFundamentals.ticker == ticker_upper))
            db_record = result.scalar_one_or_none()
            if not db_record:
                db_record = AIFundamentals(ticker=ticker_upper, story=markdown_result)
                session.add(db_record)
            else:
                db_record.story = markdown_result
            await session.commit()
            
        return {"ticker": ticker_upper, "markdown": markdown_result}
    except Exception as exc:
        return {"error": str(exc)}

@app.get("/api/fundamentals/{ticker}/porter")
@cached_async(ttl_seconds=86400) # Secondary cache
async def get_fundamental_porter(ticker: str):
    """Generates Porter's 5 Forces Analysis via Gemini and stores it in PostgreSQL."""
    ticker_upper = ticker.upper()
    from app.database import async_session
    from app.models import AIFundamentals
    from sqlalchemy import select
    
    async with async_session() as session:
        result = await session.execute(select(AIFundamentals).where(AIFundamentals.ticker == ticker_upper))
        db_record = result.scalar_one_or_none()
        if db_record and db_record.porter:
            return {"ticker": ticker_upper, "markdown": db_record.porter}
            
    try:
        from app.fundamentals import generate_porter_forces
        
        markdown_result = await generate_porter_forces(ticker)
        
        async with async_session() as session:
            result = await session.execute(select(AIFundamentals).where(AIFundamentals.ticker == ticker_upper))
            db_record = result.scalar_one_or_none()
            if not db_record:
                db_record = AIFundamentals(ticker=ticker_upper, porter=markdown_result)
                session.add(db_record)
            else:
                db_record.porter = markdown_result
            await session.commit()
            
        return {"ticker": ticker_upper, "markdown": markdown_result}
    except Exception as exc:
        return {"error": str(exc)}

@app.get("/api/fundamentals/{ticker}/competitors")
@cached_async(ttl_seconds=86400) # Secondary cache
async def get_fundamental_competitors(ticker: str):
    """Generates Top 3 Competitor Comparison via Gemini and stores it in PostgreSQL."""
    ticker_upper = ticker.upper()
    from app.database import async_session
    from app.models import AIFundamentals
    from sqlalchemy import select
    
    async with async_session() as session:
        result = await session.execute(select(AIFundamentals).where(AIFundamentals.ticker == ticker_upper))
        db_record = result.scalar_one_or_none()
        if db_record and db_record.competitors:
            return {"ticker": ticker_upper, "markdown": db_record.competitors}
            
    try:
        from app.fundamentals import generate_competitor_comparison
        
        markdown_result = await generate_competitor_comparison(ticker)
        
        async with async_session() as session:
            result = await session.execute(select(AIFundamentals).where(AIFundamentals.ticker == ticker_upper))
            db_record = result.scalar_one_or_none()
            if not db_record:
                db_record = AIFundamentals(ticker=ticker_upper, competitors=markdown_result)
                session.add(db_record)
            else:
                db_record.competitors = markdown_result
            await session.commit()
            
        return {"ticker": ticker_upper, "markdown": markdown_result}
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

# ── Portfolio Endpoints ────────────────────────────────────────

class HoldingRequest(BaseModel):
    ticker: str
    shares: float
    avg_cost_basis: float

@app.get("/api/portfolio")
async def list_portfolios():
    """List all portfolios. Creates a default one if none exist."""
    from app.database import async_session
    from app.models import Portfolio
    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(select(Portfolio).order_by(Portfolio.id))
        portfolios = result.scalars().all()

        if not portfolios:
            default = Portfolio(name="My Portfolio")
            session.add(default)
            await session.commit()
            await session.refresh(default)
            portfolios = [default]

        return [{"id": p.id, "name": p.name, "created_at": str(p.created_at)} for p in portfolios]


@app.get("/api/portfolio/{portfolio_id}")
async def get_portfolio(portfolio_id: int):
    """Get a portfolio with all holdings, enriched with live prices."""
    import yfinance as yf
    from app.database import async_session
    from app.models import Portfolio, PortfolioHolding
    from sqlalchemy import select

    async with async_session() as session:
        # Fetch portfolio
        port = await session.get(Portfolio, portfolio_id)
        if not port:
            return {"error": f"Portfolio {portfolio_id} not found"}

        # Fetch holdings
        result = await session.execute(
            select(PortfolioHolding)
            .where(PortfolioHolding.portfolio_id == portfolio_id)
            .order_by(PortfolioHolding.added_at)
        )
        holdings = result.scalars().all()

        # Enrich with live prices
        enriched = []
        total_value = 0.0
        total_cost = 0.0

        for h in holdings:
            try:
                # Check Valkey cache first
                cache_key = f"live_price:{h.ticker}"
                cached_price = await get_cache(cache_key)
                if cached_price:
                    current_price = float(cached_price)
                else:
                    import concurrent.futures
                    def _fetch_info(ticker=h.ticker):
                        return yf.Ticker(ticker).info
                    loop = asyncio.get_running_loop()
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        info = await loop.run_in_executor(pool, _fetch_info)
                    current_price = (
                        info.get("currentPrice")
                        or info.get("regularMarketPrice")
                        or info.get("previousClose")
                        or info.get("regularMarketPreviousClose")
                        or 0
                    )
                    sector = info.get("sector", "Unknown")
                    name = info.get("shortName", h.ticker)
                    if current_price:
                        await set_cache(cache_key, str(current_price), ttl_seconds=300)
                    await set_cache(f"sector:{h.ticker}", sector, ttl_seconds=86400)
                    await set_cache(f"name:{h.ticker}", name, ttl_seconds=86400)
            except Exception as exc:
                import traceback
                print(f"[portfolio] Price fetch error for {h.ticker}: {exc}")
                traceback.print_exc()
                current_price = 0

            current_value = h.shares * current_price
            cost_basis_total = h.shares * h.avg_cost_basis
            unrealized_pnl = current_value - cost_basis_total
            unrealized_pnl_pct = (unrealized_pnl / cost_basis_total * 100) if cost_basis_total > 0 else 0

            total_value += current_value
            total_cost += cost_basis_total

            # Get cached sector/name
            sector = await get_cache(f"sector:{h.ticker}") or "Unknown"
            name = await get_cache(f"name:{h.ticker}") or h.ticker

            enriched.append({
                "id": h.id,
                "ticker": h.ticker,
                "name": name,
                "sector": sector,
                "shares": h.shares,
                "avg_cost_basis": round(h.avg_cost_basis, 2),
                "current_price": round(current_price, 2),
                "current_value": round(current_value, 2),
                "cost_basis_total": round(cost_basis_total, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            })

        # Compute weight percentages
        for item in enriched:
            item["weight_pct"] = round((item["current_value"] / total_value * 100) if total_value > 0 else 0, 2)

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        # Get last updated date from transactions
        from app.models import Transaction
        last_txn_result = await session.execute(
            select(Transaction.executed_at)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at.desc())
            .limit(1)
        )
        last_txn_date = last_txn_result.scalar()

        return {
            "id": port.id,
            "name": port.name,
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "num_holdings": len(enriched),
            "last_updated": str(last_txn_date)[:10] if last_txn_date else None,
            "holdings": enriched,
        }


@app.get("/api/portfolio/{portfolio_id}/benchmarks")
async def get_portfolio_benchmarks(portfolio_id: int):
    """Compute portfolio % returns vs S&P 500 / NASDAQ, plus beta, alpha, Sharpe.
    Includes realized P&L and dividends in the total return calculation."""
    import yfinance as yf
    import pandas as pd
    import numpy as np
    import concurrent.futures
    from app.database import async_session
    from app.models import Portfolio, PortfolioHolding, Transaction
    from sqlalchemy import select, func as sqlfunc
    from datetime import datetime, timedelta

    async with async_session() as session:
        port = await session.get(Portfolio, portfolio_id)
        if not port:
            return {"error": f"Portfolio {portfolio_id} not found"}

        # Get holdings
        result = await session.execute(
            select(PortfolioHolding)
            .where(PortfolioHolding.portfolio_id == portfolio_id)
        )
        holdings = result.scalars().all()
        if not holdings:
            return {"error": "No holdings in portfolio"}

        # Get earliest transaction date (inception)
        txn_result = await session.execute(
            select(Transaction.executed_at)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at.asc())
            .limit(1)
        )
        inception_date = txn_result.scalar()

        # ── Compute realized P&L and dividends from transactions ──
        all_txns_result = await session.execute(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at.asc())
        )
        all_txns = all_txns_result.scalars().all()

        total_realized_pnl = 0.0  # Profit/loss from sells (converted to USD)
        total_dividends = 0.0     # Dividend income (converted to USD)

        for t in all_txns:
            action = (t.action or "").lower()
            fx = t.exchange_rate or 1.0  # T212 exchange rate (GBP -> USD for trades, USD -> GBP for divs)
            
            if "sell" in action and "split" not in action:
                total_realized_pnl += (t.result_in_local or 0) * fx
            elif "dividend" in action:
                total_dividends += (abs(t.total_in_local or 0) / fx) if fx > 0 else 0

    if not inception_date:
        return {"error": "No transactions found"}

    inception_str = inception_date.strftime("%Y-%m-%d")
    today = datetime.now()

    # Total Invested is the cost basis of currently held shares
    total_invested = sum(h.shares * h.avg_cost_basis for h in holdings if h.shares > 0)

    # Build ticker list + weights
    tickers = [h.ticker for h in holdings if h.shares > 0]
    if not tickers:
        return {"error": "No active holdings"}

    # Download all price data in one batch
    benchmark_tickers = ["^GSPC", "^IXIC"]
    all_tickers = tickers + benchmark_tickers

    def _download():
        data = yf.download(
            all_tickers,
            start=inception_str,
            end=(today + timedelta(days=1)).strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
        )
        if data.empty:
            return pd.DataFrame()
        # For single ticker, yfinance returns flat columns
        if len(all_tickers) == 1:
            return data
        return data["Close"] if "Close" in data.columns.get_level_values(0) else data

    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="yf_bench") as pool:
        close_df = await loop.run_in_executor(pool, _download)

    if close_df.empty:
        return {"error": "Could not fetch price data"}

    # Flatten multi-index columns if needed
    if isinstance(close_df.columns, pd.MultiIndex):
        close_df.columns = close_df.columns.get_level_values(-1)

    # Compute daily returns
    returns_df = close_df.pct_change().dropna()
    if returns_df.empty:
        return {"error": "Insufficient data for returns"}

    # Compute current portfolio value from latest prices
    current_value = 0.0
    weights = {}
    for h in holdings:
        if h.shares > 0 and h.ticker in close_df.columns:
            price = close_df[h.ticker].iloc[-1]
            if not pd.isna(price):
                val = h.shares * price
                current_value += val
                weights[h.ticker] = val  # raw value, will normalize below

    # Normalize weights
    if current_value > 0:
        weights = {k: v / current_value for k, v in weights.items()}

    # ── Total Portfolio Return (including realized + dividends) ──
    # Total return = (Unrealized P&L + Realized P&L + Dividends) / Total Invested
    total_return_pct = None
    unrealized_pnl = current_value - total_invested
    if total_invested > 0:
        total_return_pct = round(
            ((unrealized_pnl + total_realized_pnl + total_dividends) / total_invested) * 100, 2
        )

    # Weighted portfolio daily returns (for time-series comparison)
    portfolio_daily = pd.Series(0.0, index=returns_df.index)
    for ticker, weight in weights.items():
        if ticker in returns_df.columns:
            portfolio_daily += weight * returns_df[ticker].fillna(0)

    # Compute cumulative returns at various periods
    def cum_return(series, start_date=None):
        if start_date:
            series = series[series.index >= pd.Timestamp(start_date)]
        if series.empty:
            return None
        return round(float(((1 + series).cumprod().iloc[-1] - 1) * 100), 2)

    periods = {
        "1m": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
        "3m": (today - timedelta(days=90)).strftime("%Y-%m-%d"),
        "6m": (today - timedelta(days=180)).strftime("%Y-%m-%d"),
        "ytd": f"{today.year}-01-01",
        "1y": (today - timedelta(days=365)).strftime("%Y-%m-%d"),
        "since_inception": inception_str,
    }

    portfolio_returns = {}
    for period_key, start in periods.items():
        portfolio_returns[period_key] = cum_return(portfolio_daily, start)

    # Override since_inception with the total return that includes realized + dividends
    if total_return_pct is not None:
        portfolio_returns["since_inception"] = total_return_pct

    benchmarks = []
    for bm_ticker, bm_name in [("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ")]:
        if bm_ticker not in returns_df.columns:
            continue
        bm_returns = {}
        for period_key, start in periods.items():
            bm_returns[period_key] = cum_return(returns_df[bm_ticker], start)
        benchmarks.append({
            "name": bm_name,
            "ticker": bm_ticker,
            "returns": bm_returns,
        })

    # Beta, Alpha, Sharpe (annualized, using S&P 500 as market)
    beta = None
    alpha = None
    sharpe = None
    risk_free_rate = 0.04  # ~4% annual treasury rate

    if "^GSPC" in returns_df.columns:
        market_returns = returns_df["^GSPC"].fillna(0)
        # Align
        aligned = pd.DataFrame({"port": portfolio_daily, "mkt": market_returns}).dropna()
        if len(aligned) > 30:
            cov_matrix = np.cov(aligned["port"], aligned["mkt"])
            market_var = cov_matrix[1, 1]
            if market_var > 0:
                beta = round(float(cov_matrix[0, 1] / market_var), 2)

            # Annualized returns
            trading_days = len(aligned)
            port_annual = float(((1 + aligned["port"]).cumprod().iloc[-1]) ** (252 / trading_days) - 1)
            mkt_annual = float(((1 + aligned["mkt"]).cumprod().iloc[-1]) ** (252 / trading_days) - 1)

            # Alpha (Jensen's)
            if beta is not None:
                alpha = round((port_annual - (risk_free_rate + beta * (mkt_annual - risk_free_rate))) * 100, 2)

            # Sharpe
            port_std_annual = float(aligned["port"].std() * np.sqrt(252))
            if port_std_annual > 0:
                sharpe = round((port_annual - risk_free_rate) / port_std_annual, 2)

    return {
        "portfolio_return": portfolio_returns,
        "benchmarks": benchmarks,
        "beta": beta,
        "alpha": alpha,
        "sharpe_ratio": sharpe,
        "inception_date": inception_str,
        # Return breakdown
        "total_invested": round(total_invested, 2),
        "current_value": round(current_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(total_realized_pnl, 2),
        "dividend_income": round(total_dividends, 2),
        "total_return_pct": total_return_pct,
    }


@app.post("/api/portfolio/{portfolio_id}/holdings")
async def add_holding(portfolio_id: int, request: HoldingRequest):
    """Add a new holding to a portfolio."""
    from app.database import async_session
    from app.models import Portfolio, PortfolioHolding

    async with async_session() as session:
        port = await session.get(Portfolio, portfolio_id)
        if not port:
            return {"error": f"Portfolio {portfolio_id} not found"}

        holding = PortfolioHolding(
            portfolio_id=portfolio_id,
            ticker=request.ticker.upper(),
            shares=request.shares,
            avg_cost_basis=request.avg_cost_basis,
        )
        session.add(holding)
        await session.commit()
        await session.refresh(holding)
        return {"id": holding.id, "ticker": holding.ticker, "shares": holding.shares, "avg_cost_basis": holding.avg_cost_basis}


@app.put("/api/portfolio/{portfolio_id}/holdings/{holding_id}")
async def update_holding(portfolio_id: int, holding_id: int, request: HoldingRequest):
    """Update an existing holding's shares or cost basis."""
    from app.database import async_session
    from app.models import PortfolioHolding

    async with async_session() as session:
        holding = await session.get(PortfolioHolding, holding_id)
        if not holding or holding.portfolio_id != portfolio_id:
            return {"error": "Holding not found"}

        holding.ticker = request.ticker.upper()
        holding.shares = request.shares
        holding.avg_cost_basis = request.avg_cost_basis
        await session.commit()
        return {"id": holding.id, "ticker": holding.ticker, "shares": holding.shares, "avg_cost_basis": holding.avg_cost_basis}


@app.delete("/api/portfolio/{portfolio_id}/holdings/{holding_id}")
async def delete_holding(portfolio_id: int, holding_id: int):
    """Remove a holding from a portfolio."""
    from app.database import async_session
    from app.models import PortfolioHolding

    async with async_session() as session:
        holding = await session.get(PortfolioHolding, holding_id)
        if not holding or holding.portfolio_id != portfolio_id:
            return {"error": "Holding not found"}

        await session.delete(holding)
        await session.commit()
        return {"deleted": True, "id": holding_id}



# ── Trading 212 CSV Import ─────────────────────────────────────

@app.post("/api/portfolio/{portfolio_id}/import/csv")
async def import_csv(portfolio_id: int, file: UploadFile = File(...)):
    """
    Import transactions from a Trading 212 CSV export.
    Stores every transaction row (buy/sell/dividend) with dedup by external_id.
    Recomputes holdings from the full transaction log.
    """
    from app.database import async_session
    from app.models import Portfolio, PortfolioHolding, Transaction
    from app.t212_import import parse_t212_transactions, compute_holdings
    from sqlalchemy import select, delete

    # Validate file type
    if file.filename and not file.filename.lower().endswith('.csv'):
        return {"error": "Please upload a CSV file"}

    try:
        raw_bytes = await file.read()
        file_content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return {"error": "Could not decode file. Please ensure it is a UTF-8 CSV."}

    try:
        transactions = parse_t212_transactions(file_content)
    except ValueError as exc:
        return {"error": str(exc)}

    if not transactions:
        return {"error": "No transactions found in the CSV file."}

    async with async_session() as session:
        # Verify portfolio exists
        port = await session.get(Portfolio, portfolio_id)
        if not port:
            return {"error": f"Portfolio {portfolio_id} not found"}

        # Get existing external_ids for this portfolio to skip duplicates
        result = await session.execute(
            select(Transaction.external_id)
            .where(Transaction.portfolio_id == portfolio_id)
            .where(Transaction.external_id.isnot(None))
        )
        existing_ids = {row[0] for row in result.fetchall()}

        new_count = 0
        skipped_count = 0

        for txn in transactions:
            ext_id = txn.get("external_id")
            # Skip if we've already imported this transaction
            if ext_id and ext_id in existing_ids:
                skipped_count += 1
                continue

            record = Transaction(
                portfolio_id=portfolio_id,
                external_id=ext_id,
                action=txn["action"],
                ticker=txn["ticker"],
                name=txn.get("name", ""),
                isin=txn.get("isin", ""),
                shares=txn["shares"],
                price_per_share=txn["price_per_share"],
                currency=txn.get("currency", ""),
                exchange_rate=txn.get("exchange_rate"),
                total_in_local=txn.get("total_in_local"),
                result_in_local=txn.get("result_in_local"),
                executed_at=txn["executed_at"],
            )
            session.add(record)
            if ext_id:
                existing_ids.add(ext_id)
            new_count += 1

        await session.flush()

        # Recompute holdings from ALL transactions for this portfolio
        all_txns_result = await session.execute(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at)
        )
        all_txns = [
            {
                "action": t.action,
                "ticker": t.ticker,
                "shares": t.shares,
                "price_per_share": t.price_per_share,
                "name": t.name,
            }
            for t in all_txns_result.scalars().all()
        ]

        computed = compute_holdings(all_txns)

        # Clear existing holdings and rewrite
        await session.execute(
            delete(PortfolioHolding)
            .where(PortfolioHolding.portfolio_id == portfolio_id)
        )

        for h in computed:
            if h["shares"] > 0:
                session.add(PortfolioHolding(
                    portfolio_id=portfolio_id,
                    ticker=h["ticker"],
                    shares=h["shares"],
                    avg_cost_basis=h["avg_cost_basis"],
                ))

        await session.commit()

    return {
        "new_transactions": new_count,
        "skipped": skipped_count,
        "total_in_csv": len(transactions),
        "holdings_count": len([h for h in computed if h["shares"] > 0]),
        "total_realized_pnl": round(sum(h["realized_pnl"] for h in computed), 2),
    }


@app.get("/api/portfolio/{portfolio_id}/transactions")
async def get_transactions(
    portfolio_id: int,
    ticker: str = Query(default=None, description="Filter by ticker"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Get paginated transaction history for a portfolio."""
    from app.database import async_session
    from app.models import Transaction
    from sqlalchemy import select, func as sqlfunc

    async with async_session() as session:
        query = (
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
        )
        count_query = (
            select(sqlfunc.count(Transaction.id))
            .where(Transaction.portfolio_id == portfolio_id)
        )

        if ticker:
            query = query.where(Transaction.ticker == ticker.upper())
            count_query = count_query.where(Transaction.ticker == ticker.upper())

        # Get total count
        total = (await session.execute(count_query)).scalar() or 0

        # Get page of results
        query = query.order_by(Transaction.executed_at.desc()).limit(limit).offset(offset)
        result = await session.execute(query)
        txns = result.scalars().all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "transactions": [
                {
                    "id": t.id,
                    "external_id": t.external_id,
                    "action": t.action,
                    "ticker": t.ticker,
                    "name": t.name,
                    "shares": t.shares,
                    "price_per_share": round(t.price_per_share, 4),
                    "currency": t.currency,
                    "exchange_rate": round(t.exchange_rate, 6) if t.exchange_rate else None,
                    "total_in_local": round(t.total_in_local, 2) if t.total_in_local else None,
                    "result_in_local": round(t.result_in_local, 2) if t.result_in_local else None,
                    "executed_at": str(t.executed_at),
                }
                for t in txns
            ],
        }


@app.get("/api/portfolio/{portfolio_id}/realized")
async def get_realized_summary(portfolio_id: int):
    """
    Get aggregated realized P&L from sells and dividend income.
    Returns per-ticker breakdowns and totals.
    """
    from app.database import async_session
    from app.models import Transaction
    from sqlalchemy import select

    async with async_session() as session:
        result = await session.execute(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at)
        )
        txns = result.scalars().all()

        # ── Realized P&L from sells ──────────────────────────
        sell_actions = {'market sell', 'limit sell'}
        sells_by_ticker: dict = {}

        for t in txns:
            if t.action.lower() not in sell_actions:
                continue
            ticker = t.ticker
            if ticker not in sells_by_ticker:
                sells_by_ticker[ticker] = {
                    "ticker": ticker,
                    "name": t.name or ticker,
                    "total_proceeds": 0.0,
                    "total_realized_pnl": 0.0,
                    "total_shares_sold": 0.0,
                    "num_trades": 0,
                    "trades": [],
                }
            entry = sells_by_ticker[ticker]
            proceeds_local = t.total_in_local or 0
            result_local = t.result_in_local or 0
            entry["total_proceeds"] += proceeds_local
            entry["total_realized_pnl"] += result_local
            entry["total_shares_sold"] += t.shares
            entry["num_trades"] += 1
            entry["trades"].append({
                "date": str(t.executed_at)[:10] if t.executed_at else "",
                "shares": round(t.shares, 4),
                "price": round(t.price_per_share, 2),
                "proceeds": round(proceeds_local, 2),
                "pnl": round(result_local, 2),
            })

        realized_list = []
        for data in sorted(sells_by_ticker.values(), key=lambda x: -abs(x["total_realized_pnl"])):
            realized_list.append({
                "ticker": data["ticker"],
                "name": data["name"],
                "total_proceeds": round(data["total_proceeds"], 2),
                "total_realized_pnl": round(data["total_realized_pnl"], 2),
                "total_shares_sold": round(data["total_shares_sold"], 4),
                "num_trades": data["num_trades"],
                "trades": data["trades"],
            })

        # ── Dividend income ──────────────────────────────────
        dividends_by_ticker: dict = {}

        for t in txns:
            if not t.action.lower().startswith("dividend"):
                continue
            ticker = t.ticker
            if ticker not in dividends_by_ticker:
                dividends_by_ticker[ticker] = {
                    "ticker": ticker,
                    "name": t.name or ticker,
                    "total_income": 0.0,
                    "total_withholding_tax": 0.0,
                    "num_payments": 0,
                    "payments": [],
                }
            entry = dividends_by_ticker[ticker]
            income_local = t.total_in_local or 0
            entry["total_income"] += income_local
            entry["num_payments"] += 1
            entry["payments"].append({
                "date": str(t.executed_at)[:10] if t.executed_at else "",
                "shares": round(t.shares, 4),
                "per_share": round(t.price_per_share, 6),
                "income": round(income_local, 2),
            })

        dividend_list = []
        for data in sorted(dividends_by_ticker.values(), key=lambda x: -x["total_income"]):
            dividend_list.append({
                "ticker": data["ticker"],
                "name": data["name"],
                "total_income": round(data["total_income"], 2),
                "num_payments": data["num_payments"],
                "payments": data["payments"],
            })

        total_realized = round(sum(s["total_realized_pnl"] for s in realized_list), 2)
        total_dividends = round(sum(d["total_income"] for d in dividend_list), 2)

        return {
            "total_realized_pnl": total_realized,
            "total_dividend_income": total_dividends,
            "total_income": round(total_realized + total_dividends, 2),
            "realized": realized_list,
            "dividends": dividend_list,
        }


# ── Main ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
