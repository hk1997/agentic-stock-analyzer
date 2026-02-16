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

@tool
def search_web(query: str):
    """Searches the web for news, reports, or general information.
    Use this to find *reasons* for stock moves, recent news, or current events.
    """
    print(f"\n   [System] Tool triggered: Searching web for '{query}'...")
    from langchain_community.tools import DuckDuckGoSearchRun
    try:
        search = DuckDuckGoSearchRun()
        return search.invoke(query)
    except Exception as e:
        return f"Error searching web: {e}"

@tool
def get_financial_metrics(ticker: str):
    """Fetches key financial ratios and metrics for a company.
    Useful for fundamental analysis.
    Returns: P/E, PEG, PriceToBook, Profit Margins, ROE, Revenue Growth, etc.
    """
    print(f"\n   [System] Tool triggered: Fetching financial metrics for {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Filter for key metrics to avoid overwhelming the LLM
        metrics = {
            "Trailing P/E": info.get("trailingPE"),
            "Forward P/E": info.get("forwardPE"),
            "PEG Ratio": info.get("pegRatio"),
            "Price to Book": info.get("priceToBook"),
            "Debt to Equity": info.get("debtToEquity"),
            "Profit Margins": info.get("profitMargins"),
            "Return on Equity": info.get("returnOnEquity"),
            "Revenue Growth": info.get("revenueGrowth"),
            "Enterprise Value/EBITDA": info.get("enterpriseToEbitda"),
            "Beta": info.get("beta")
        }
        return str(metrics)
    except Exception as e:
        return f"Error fetching metrics for {ticker}: {e}"

@tool
def get_company_info(ticker: str):
    """Fetches company profile and business summary.
    Returns: Sector, Industry, Full Time Employees, Business Summary.
    """
    print(f"\n   [System] Tool triggered: Fetching company info for {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        profile = {
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "employees": info.get("fullTimeEmployees"),
            "summary": info.get("longBusinessSummary"),
            "city": info.get("city"),
            "country": info.get("country")
        }
        return str(profile)
    except Exception as e:
        return f"Error fetching profile for {ticker}: {e}"

@tool
def get_free_cash_flow(ticker: str):
    """Fetches the most recent Free Cash Flow (FCF) for a company.
    FCF = Operating Cash Flow - Capital Expenditure.
    """
    print(f"\n   [System] Tool triggered: Fetching FCF for {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        # cashflow dataframe: columns are dates, rows are metrics
        cf = stock.cashflow
        if cf.empty:
             return f"Error: No cash flow data found for {ticker}."
             
        # Try to find Free Cash Flow row
        if "Free Cash Flow" in cf.index:
            recent_fcf = cf.loc["Free Cash Flow"].iloc[0]
            return f"{recent_fcf}"
        
        # Calculate manually if missing: OCF - CapEx
        # CapEx is often negative in yfinance, so OCF + CapEx (if negative) or OCF - CapEx (if positive)
        # usually yfinance has 'Capital Expenditure' as negative number.
        if "Operating Cash Flow" in cf.index and "Capital Expenditure" in cf.index:
            ocf = cf.loc["Operating Cash Flow"].iloc[0]
            capex = cf.loc["Capital Expenditure"].iloc[0] 
            # If capex is positive for some reason, subtract it. If negative, add it.
            # Standard accounting: FCF = OCF - (-CapEx) = OCF + CapEx (if CapEx is negative)
            fcf = ocf + capex 
            return f"{fcf}"
            
        return f"Error: Could not calculate FCF for {ticker}."
    except Exception as e:
        return f"Error fetching FCF for {ticker}: {e}"

@tool
def calculate_intrinsic_value(ticker: str):
    """Calculates the Intrinsic Value of a company using a 5-Year DCF model.
    Uses systematically derived assumptions:
    - Growth Rate: Based on analyst estimates (capped at 15%).
    - Discount Rate: Based on CAPM (Risk Free Rate + Beta * Risk Premium).
    - Terminal Growth: 3% (Global GDP).
    """
    print(f"\n   [System] Tool triggered: Calculating Intrinsic Value (DCF) for {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # 1. Get Free Cash Flow
        fcf_str = get_free_cash_flow.invoke(ticker)
        if "Error" in fcf_str: return fcf_str
        fcf = float(fcf_str)
        
        # 2. Get Beta and calculate Discount Rate (CAPM)
        beta = info.get("beta", 1.0)
        risk_free_rate = 0.042  # 4.2% approximation for 10Y Treasury
        equity_risk_premium = 0.05 # 5%
        discount_rate = risk_free_rate + (beta * equity_risk_premium)
        
        # 3. Get Growth Rate
        # Try revenueGrowth, earningsGrowth, or pegRatio implied growth
        growth_est = info.get("revenueGrowth", 0.05)
        if growth_est is None: growth_est = 0.05
        
        # Cap growth at 15% to be conservative
        growth_rate = min(growth_est, 0.15)
        if growth_rate < 0: growth_rate = 0.02 # Assume minimal growth if negative
        
        terminal_growth = 0.03
        shares_outstanding = info.get("sharesOutstanding")
        if not shares_outstanding: return f"Error: No shares data for {ticker}"
        
        # 4. DCF Calculation
        future_cash_flows = []
        for year in range(1, 6):
            projected_fcf = fcf * ((1 + growth_rate) ** year)
            discounted_fcf = projected_fcf / ((1 + discount_rate) ** year)
            future_cash_flows.append(discounted_fcf)
            
        # Terminal Value
        terminal_value = (fcf * ((1 + growth_rate) ** 5) * (1 + terminal_growth)) / (discount_rate - terminal_growth)
        discounted_tv = terminal_value / ((1 + discount_rate) ** 5)
        
        total_enterprise_value = sum(future_cash_flows) + discounted_tv
        
        # Equity Value (simplified, assuming Net Debt ~ 0 for rough estimate or user can refine)
        # Ideally: Equity Value = Enterprise Value + Cash - Debt
        # For simplicity in this tool, we'll treat TEV as Equity Value or just approximate
        # Let's try to get net debt if possible
        total_cash = info.get("totalCash", 0)
        total_debt = info.get("totalDebt", 0)
        equity_value = total_enterprise_value + total_cash - total_debt
        
        fair_value_per_share = equity_value / shares_outstanding
        current_price = info.get("currentPrice")
        
        margin_of_safety = (1 - (current_price / fair_value_per_share)) * 100
        
        return (f"--- DCF Valuation for {ticker} ---\n"
                f"Current Price: ${current_price:.2f}\n"
                f"Estimated Fair Value: ${fair_value_per_share:.2f}\n"
                f"Margin of Safety: {margin_of_safety:.2f}%\n\n"
                f"Assumptions Used:\n"
                f"- Recent FCF: ${fcf:,.0f}\n"
                f"- Growth Rate (Capped): {growth_rate*100:.2f}% (Analyst Est: {growth_est*100 if growth_est else 'N/A'}%)\n"
                f"- Discount Rate (CAPM): {discount_rate*100:.2f}% (Beta: {beta})\n"
                f"- Terminal Growth: {terminal_growth*100:.1f}%")
        
    except Exception as e:
        return f"Error calculating DCF for {ticker}: {e}"

# Export all tools
tools = [
    fetch_stock_price, 
    calculate_rsi, 
    calculate_sma, 
    calculate_macd, 
    search_web,
    get_financial_metrics,
    get_company_info,
    get_free_cash_flow,
    calculate_intrinsic_value
]
