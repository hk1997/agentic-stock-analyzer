import os
from typing import Optional
from langchain_core.tools import tool
from edgar import set_identity, Company

# Set user identity for SEC Edgar API (required)
# Should ideally be a real email, but this works for demo purposes.
set_identity("Agentic Analyzer info@hardikkhandelwal.com")

def _fetch_filing(ticker: str, form_type: str) -> str:
    """Helper function to fetch the latest filing of a specific type."""
    try:
        company = Company(ticker)
        if not company:
            return f"Failed to find SEC company data for ticker: {ticker}"
            
        # Get all filings of the specified form type
        filings = company.get_filings(form=form_type)
        if filings.empty:
            return f"No {form_type} filings found for {ticker}."
            
        # Get the latest filing
        latest = filings[0]
        
        # We fetch the text representation so the LLM can process it. 
        # Note: 10-K/Qs can be extremely long. We might want to truncate or extract sections.
        # For now, we extract the first 30,000 characters to prevent context window explosion.
        # Ideally, we should parse 'Item 7. Management's Discussion and Analysis'.
        text = latest.text()
        
        # Extremely rough truncation for context size limits
        MAX_CHARS = 30000 
        snippet = text[:MAX_CHARS] if text else "No text could be extracted."
        
        return f"--- LATEST {form_type} FOR {ticker} (Truncated) ---\n\n{snippet}"

    except Exception as e:
        print(f"   [Error] SEC Edgar fetch failed: {e}")
        return f"Error retrieving {form_type} for {ticker}: {e}"

@tool
def get_latest_10k(ticker: str) -> str:
    """
    Retrieves the most recent SEC 10-K (Annual Report) for a given stock ticker. 
    Use this to understand a company's long-term business strategy, major risk factors, 
    and comprehensive management discussion.
    """
    return _fetch_filing(ticker, "10-K")

@tool
def get_latest_10q(ticker: str) -> str:
    """
    Retrieves the most recent SEC 10-Q (Quarterly Report) for a given stock ticker.
    Use this to get the latest quarterly financial results, management commentary on recent operations, 
    and short-term risk updates.
    """
    return _fetch_filing(ticker, "10-Q")
