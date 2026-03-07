# app/fundamentals.py
import yfinance as yf
from langchain_core.messages import SystemMessage, HumanMessage
from .llm import get_llm

import functools

from .prompts import (
    BUSINESS_MODEL_STORY_PROMPT,
    PORTER_5_FORCES_PROMPT,
    COMPETITOR_COMPARISON_PROMPT
)

import datetime
from sqlalchemy import select
from .database import async_session
from .models import CompanyProfile

async def _get_background_context(ticker: str) -> dict:
    """
    Fetches high-level company profile data from PostgreSQL.
    If missing or older than 30 days, fetches fresh data via yfinance and persists it.
    """
    ticker_upper = ticker.upper()
    try:
        async with async_session() as session:
            # 1. Check Database first
            stmt = select(CompanyProfile).where(CompanyProfile.ticker == ticker_upper)
            result = await session.execute(stmt)
            profile = result.scalar_one_or_none()
            
            # Re-fetch if older than 30 days
            now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) # func.now() returns naive UTC in asyncpg by default
            needs_update = True
            if profile and profile.updated_at:
                age = now - profile.updated_at
                if age.days < 30:
                    needs_update = False
                    
            if not needs_update and profile:
                return {
                    "ticker": profile.ticker,
                    "company_name": profile.name or ticker_upper,
                    "sector": profile.sector or "Unknown",
                    "industry": profile.industry or "Unknown",
                    "longBusinessSummary": profile.summary or "No summary available."
                }
                
            # 2. Fetch fresh from yfinance (blocking, so run in executor)
            import asyncio
            import concurrent.futures
            loop = asyncio.get_running_loop()
            
            def fetch_yf():
                return yf.Ticker(ticker_upper).info
                
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                info = await loop.run_in_executor(executor, fetch_yf)
                
            # 3. Upsert into database
            if not profile:
                profile = CompanyProfile(ticker=ticker_upper)
                session.add(profile)
                
            profile.name = info.get("shortName", ticker_upper)
            profile.sector = info.get("sector", "Unknown")
            profile.industry = info.get("industry", "Unknown")
            profile.summary = info.get("longBusinessSummary", "No summary available.")
            profile.employees = info.get("fullTimeEmployees")
            profile.city = info.get("city")
            profile.country = info.get("country")
            profile.updated_at = now
            
            await session.commit()
            
            return {
                "ticker": profile.ticker,
                "company_name": profile.name,
                "sector": profile.sector,
                "industry": profile.industry,
                "longBusinessSummary": profile.summary
            }
            
    except Exception as e:
        print(f"Error fetching/saving fundamental info for {ticker}: {e}")
        return {
            "ticker": ticker_upper,
            "company_name": ticker_upper,
            "sector": "Unknown",
            "industry": "Unknown",
            "longBusinessSummary": "No background available."
        }

async def _invoke_narrative_model(ticker: str, prompt_template: str) -> str:
    """
    Fetches the static background context asynchronously, formats it into the prompt,
    and returns the LLM's generated markdown response.
    """
    context = await _get_background_context(ticker)
    
    # We heavily ground the model by passing the official SEC/Yahoo finance standard description
    background_text = f"""
Sector: {context['sector']}
Industry: {context['industry']}
Target Summary: {context['longBusinessSummary']}
    """
    
    formatted_prompt = prompt_template.format(
        ticker=context['ticker'],
        company_name=context['company_name'],
        background_info=background_text
    )
    
    # Instantiate the LLM using the centralized factory to support dynamic fallbacks (e.g. Groq)
    # We pass temperature=0.7 to allow slight creativity for analogies.
    llm = get_llm(temperature=0.7)
    
    messages = [
        SystemMessage(content=formatted_prompt),
        HumanMessage(content=f"Please analyze {context['company_name']} according to your strict structure.")
    ]
    
    try:
        response = llm.invoke(messages)
        return response.content
    except Exception as e:
        return f"Error generating narrative: {e}"

async def generate_business_story(ticker: str) -> str:
    return await _invoke_narrative_model(ticker, BUSINESS_MODEL_STORY_PROMPT)

async def generate_porter_forces(ticker: str) -> str:
    return await _invoke_narrative_model(ticker, PORTER_5_FORCES_PROMPT)

async def generate_competitor_comparison(ticker: str) -> str:
    return await _invoke_narrative_model(ticker, COMPETITOR_COMPARISON_PROMPT)
