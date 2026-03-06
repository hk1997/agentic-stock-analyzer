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

@functools.lru_cache(maxsize=32)
def _get_background_context(ticker: str) -> dict:
    """Fetches high-level company profile data via yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            "ticker": ticker.upper(),
            "company_name": info.get("shortName", ticker.upper()),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "longBusinessSummary": info.get("longBusinessSummary", "No summary available.")
        }
    except Exception as e:
        print(f"Error fetching fundamental info for {ticker}: {e}")
        return {
            "ticker": ticker.upper(),
            "company_name": ticker.upper(),
            "sector": "Unknown",
            "industry": "Unknown",
            "longBusinessSummary": "No background available."
        }

def _invoke_narrative_model(ticker: str, prompt_template: str) -> str:
    """
    Fetches the static background context, formats it into the highly structured prompt,
    and returns the LLM's generated markdown response.
    """
    context = _get_background_context(ticker)
    
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

def generate_business_story(ticker: str) -> str:
    return _invoke_narrative_model(ticker, BUSINESS_MODEL_STORY_PROMPT)

def generate_porter_forces(ticker: str) -> str:
    return _invoke_narrative_model(ticker, PORTER_5_FORCES_PROMPT)

def generate_competitor_comparison(ticker: str) -> str:
    return _invoke_narrative_model(ticker, COMPETITOR_COMPARISON_PROMPT)
