import asyncio
import os
import yfinance as yf
from fastapi import APIRouter, Query, BackgroundTasks, HTTPException
from pydantic import BaseModel
from app.cache import get_cache, set_cache, cached_async
from app.tasks import log_user_query, trigger_jit_fundamentals, _ingest_price_history

router = APIRouter(prefix="/api", tags=["market"])

CACHE_TTL = 300

class BacktestRequestAPI(BaseModel):
    ticker: str
    strategies: list[str] = ["sma_crossover"]
    initial_capital: float = 10000.0
    days: int = 365
    stop_loss_pct: float = 0.0

@router.get("/stock/{ticker}")
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
        import concurrent.futures

        yf_period = "1mo" if period == "10d" else period

        def fetch_info():
            return yf.Ticker(ticker.upper()).info or {}

        def fetch_history():
            return yf.Ticker(ticker.upper()).history(period=yf_period)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="yf_worker") as yf_executor:
            loop = asyncio.get_running_loop()
            info, hist = await asyncio.gather(
                loop.run_in_executor(yf_executor, fetch_info),
                loop.run_in_executor(yf_executor, fetch_history)
            )

        if hist.empty:
            return {"error": f"No data found for ticker '{ticker}'"}
            
        background_tasks.add_task(_ingest_price_history, ticker)
            
        if period == "10d" and len(hist) > 10:
            hist = hist.tail(10)

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

@router.get("/indicators/{ticker}")
@cached_async(ttl_seconds=300)
async def get_stock_indicators(ticker: str, background_tasks: BackgroundTasks, period: str = Query("1y", pattern="^(1mo|3mo|6mo|1y|2y|5y|max)$")):
    """
    Calculates technical indicators for the frontend charts.
    """
    background_tasks.add_task(log_user_query, ticker, "indicators")
    
    try:
        import pandas as pd
        import concurrent.futures

        def fetch_history():
            return yf.Ticker(ticker.upper()).history(period=period)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5, thread_name_prefix="yf_ind_worker") as executor:
            loop = asyncio.get_running_loop()
            hist = await loop.run_in_executor(executor, fetch_history)

        if hist.empty:
            return {"error": f"No data found for ticker '{ticker}'"}

        close = hist["Close"]
        
        sma20 = close.rolling(window=20).mean()
        sma50 = close.rolling(window=50).mean()
        sma200 = close.rolling(window=200).mean()
        
        ema20 = close.ewm(span=20, adjust=False).mean()
        
        std20 = close.rolling(window=20).std(ddof=0)
        upper_band = sma20 + (std20 * 2)
        lower_band = sma20 - (std20 * 2)
        
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal

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

@router.post("/backtest")
@cached_async(ttl_seconds=3600)
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

@router.get("/levels/{ticker}")
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

@router.get("/fundamentals/{ticker}/story")
@cached_async(ttl_seconds=86400)
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

@router.get("/fundamentals/{ticker}/porter")
@cached_async(ttl_seconds=86400)
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

@router.get("/fundamentals/{ticker}/competitors")
@cached_async(ttl_seconds=86400)
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

@router.get("/news/{ticker}")
@cached_async(ttl_seconds=3600)
async def get_recent_news(ticker: str):
    """Fetches recent news articles for the ticker using DuckDuckGo search."""
    try:
        from duckduckgo_search import DDGS
        import concurrent.futures
        
        def _fetch_news():
            ddgs = DDGS()
            results = ddgs.news(f"{ticker} stock news", max_results=10)
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

@router.get("/news/{ticker}/sentiment")
@cached_async(ttl_seconds=3600)
async def get_news_sentiment(ticker: str):
    """Fetches recent news and generates an AI sentiment summary."""
    try:
        from app.llm import get_llm
        from langchain_core.messages import HumanMessage
        from duckduckgo_search import DDGS
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

@router.get("/filings/{ticker}")
@cached_async(ttl_seconds=86400)
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

@router.get("/filings/{ticker}/mda")
@cached_async(ttl_seconds=604800)
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

@router.get("/filings/{ticker}/risks")
@cached_async(ttl_seconds=604800)
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

@router.get("/valuation/dcf/{ticker}")
@cached_async(ttl_seconds=86400)
async def get_dcf_valuation(ticker: str):
    """Calculates the DCF fair value of a ticker."""
    try:
        from app.tools import calculate_intrinsic_value
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            loop = asyncio.get_running_loop()
            dcf_result = await loop.run_in_executor(executor, calculate_intrinsic_value.invoke, {"ticker": ticker})
            
        return {"ticker": ticker.upper(), "valuation": dcf_result}
    except Exception as exc:
        return {"error": str(exc)}

@router.get("/valuation/ddm/{ticker}")
@cached_async(ttl_seconds=86400)
async def get_ddm_valuation(ticker: str):
    """Calculates the DDM fair value of a ticker."""
    try:
        from app.tools import calculate_ddm
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            loop = asyncio.get_running_loop()
            ddm_result = await loop.run_in_executor(executor, calculate_ddm.invoke, {"ticker": ticker})
            
        return {"ticker": ticker.upper(), "valuation": ddm_result}
    except Exception as exc:
        return {"error": str(exc)}

@router.get("/stock/{ticker}/risk")
@cached_async(ttl_seconds=86400)
async def get_stock_risk(ticker: str):
    """Calculates risk metrics (volatility, Sharpe, max drawdown) for a stock."""
    try:
        from app.tools import get_risk_metrics
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            loop = asyncio.get_running_loop()
            risk_result = await loop.run_in_executor(executor, get_risk_metrics.invoke, {"ticker": ticker})
            
        return {"ticker": ticker.upper(), "risk": risk_result}
    except Exception as exc:
        return {"error": str(exc)}


