import yfinance as yf
import pandas as pd
from langchain_core.tools import tool
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=10)
def _get_stock_data(ticker: str, days: int = 100) -> pd.DataFrame:
    """Helper to fetch and cache stock data to avoid spamming the API.
    
    Args:
        ticker: Stock symbol
        days: Number of days of history to fetch (default 100 for indicators)
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Download data
    stock = yf.Ticker(ticker)
    hist = stock.history(start=start_date, end=end_date, interval="1d")
    return hist

@tool
def fetch_stock_price(ticker: str, days: int = 1):
    """Fetches the stock price for a given ticker. 
    Can return the current price or a history of prices over the last n days.
    
    Args:
        ticker: The stock ticker symbol (e.g., AAPL).
        days: Number of days to fetch history for (default is 1, which returns current price).
    """
    print(f"\n   [System] Tool triggered: Fetching price for {ticker} (days={days})...")
    try:
        # Fetch enough data
        hist = _get_stock_data(ticker, days=max(days, 5)) # Fetch a bit more to be safe
        
        if hist.empty:
            return f"Error: Could not find price data for {ticker}."
        
        if days == 1:
            price = hist['Close'].iloc[-1]
            return f"{price:.2f}"
            
        # Return last n days formatted
        recent = hist['Close'].tail(days)
        return recent.to_string()
        
    except Exception as e:
        return f"Error fetching price for {ticker}: {e}"

@tool
def calculate_rsi(ticker: str, window: int = 14):
    """Calculates the Relative Strength Index (RSI) for a stock.
    RSI > 70 generally indicates overbought, RSI < 30 indicates oversold.
    """
    print(f"\n   [System] Tool triggered: Calculating RSI for {ticker}...")
    try:
        # We need enough history for the window
        hist = _get_stock_data(ticker, days=window * 4) 
        if hist.empty: return f"Error: No data for {ticker}"
        
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1]
        return f"{current_rsi:.2f}"
    except Exception as e:
        return f"Error calculating RSI: {e}"

@tool
def calculate_sma(ticker: str, window: int = 20):
    """Calculates the Simple Moving Average (SMA) for a stock."""
    print(f"\n   [System] Tool triggered: Calculating SMA({window}) for {ticker}...")
    try:
        hist = _get_stock_data(ticker, days=window * 3)
        if hist.empty: return f"Error: No data for {ticker}"
        
        sma = hist['Close'].rolling(window=window).mean()
        current_sma = sma.iloc[-1]
        return f"{current_sma:.2f}"
    except Exception as e:
        return f"Error calculating SMA: {e}"

@tool
def calculate_macd(ticker: str):
    """Calculates MACD (Moving Average Convergence Divergence) indicators.
    Returns the MACD Line, Signal Line, and Histogram.
    """
    print(f"\n   [System] Tool triggered: Calculating MACD for {ticker}...")
    try:
        hist = _get_stock_data(ticker, days=100)
        if hist.empty: return f"Error: No data for {ticker}"
        
        # Standard MACD parameters: 12, 26, 9
        exp1 = hist['Close'].ewm(span=12, adjust=False).mean()
        exp2 = hist['Close'].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal
        
        return (f"MACD Line: {macd.iloc[-1]:.2f}\n"
                f"Signal Line: {signal.iloc[-1]:.2f}\n"
                f"Histogram: {histogram.iloc[-1]:.2f}")
    except Exception as e:
        return f"Error calculating MACD: {e}"

# Export all tools
tools = [fetch_stock_price, calculate_rsi, calculate_sma, calculate_macd]
