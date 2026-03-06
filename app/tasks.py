import asyncio
import os
import json
import logging
import datetime
from sqlalchemy import select, func, text
import pandas as pd
import yfinance as yf

from app.database import async_session
from app.models import UserQueryLog, StockDailyPrice, CompanyProfile
from app.cache import get_cache, set_cache

logger = logging.getLogger(__name__)

async def _get_top_tickers(limit: int = 10, days: int = 7) -> list[str]:
    """Dynamically get the top queried tickers from TimescaleDB."""
    try:
        async with async_session() as session:
            # Query the logs for the most frequent tickers in the last N days
            time_threshold = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
            stmt = (
                select(UserQueryLog.ticker, func.count(UserQueryLog.id).label('count'))
                .where(UserQueryLog.timestamp >= time_threshold)
                .group_by(UserQueryLog.ticker)
                .order_by(func.count(UserQueryLog.id).desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            top_tickers = [row.ticker for row in result.all()]
            
            # If we don't have enough data, fall back to some defaults
            defaults = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "BRK-B", "JPM", "V"]
            for default in defaults:
                if len(top_tickers) >= limit:
                    break
                if default not in top_tickers:
                    top_tickers.append(default)
                    
            return top_tickers
            
    except Exception as e:
        logger.error(f"Error fetching top tickers: {e}")
        return ["AAPL", "MSFT", "NVDA"]

async def update_active_tickers_prices():
    """Lightweight background task to silently update TimescaleDB prices for active tickers."""
    top_tickers = await _get_top_tickers(limit=10, days=1) # Only care about recent activity
    logger.info(f"Background refresh: Updating prices for active tickers: {top_tickers}")

    # Process sequentially in background to minimize DB/Network contention
    for ticker in top_tickers:
        await _ingest_price_history(ticker)

async def _ingest_price_history(ticker: str):
    """Fetches yfinance data and upserts into TimescaleDB hypertable."""
    try:
        # We use a threadpool for the blocking yfinance call
        loop = asyncio.get_running_loop()
        hist = await loop.run_in_executor(None, lambda: yf.Ticker(ticker).history(period="1mo"))
        
        if hist.empty:
            return

        async with async_session() as session:
            for date, row in hist.iterrows():
                # Convert pandas timestamp to standard python datetime with strict UTC
                dt = date.to_pydatetime()
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                
                # TimescaleDB Upsert logic
                stmt = text("""
                    INSERT INTO stock_daily_prices (time, ticker, open, high, low, close, volume)
                    VALUES (:time, :ticker, :open, :high, :low, :close, :volume)
                    ON CONFLICT (time, ticker) DO UPDATE SET
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume;
                """)
                await session.execute(stmt, {
                    "time": dt,
                    "ticker": ticker,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"])
                })
            await session.commit()
    except Exception as e:
        logger.error(f"Error ingesting price history for {ticker}: {e}")

# _prefetch_fundamentals removed intentionally to avoid rate limits
# Fundamentals are now strictly generated JIT (Just-In-Time) when requested

async def log_user_query(ticker: str, query_type: str = "general"):
    """Fire-and-forget task to log user interest so the Top 10 script picks it up."""
    try:
        async with async_session() as session:
            log = UserQueryLog(
                ticker=ticker.upper(),
                query_type=query_type
            )
            session.add(log)
            await session.commit()
    except Exception as e:
        logger.error(f"Failed to log query for {ticker}: {e}")

async def trigger_jit_fundamentals(ticker: str):
    """
    Just-in-Time generation queue for LLM Fundamentals.
    """
    # This was previously kicking off the 3 heavy requests at once. We'll leave it empty 
    # to let the lazy loading endpoints handle it when a user explicitly requests it.
    pass
