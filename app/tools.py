import yfinance as yf
from langchain_core.tools import tool

@tool
def fetch_stock_price(ticker: str):
    """Fetches the current stock price for a given ticker symbol (e.g., AAPL, TSLA).
    
    Args:
        ticker: The stock ticker symbol.
    """
    print(f"\n   [System] Tool triggered: Fetching price for {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        # Verify data exists by checking history
        hist = stock.history(period="1d")
        if hist.empty:
            return f"Error: Could not find price data for {ticker}. Please check the symbol."
        price = hist['Close'].iloc[-1]
        return f"{price:.2f}"
    except Exception as e:
        return f"Error fetching price for {ticker}: {e}"

# Export the list of tools
tools = [fetch_stock_price]
