import os
import sys
import asyncio
import json
import httpx
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select

# Ensure project root is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp.server.fastmcp import FastMCP

# Import DB and auth helpers to generate token
from app.database import async_session
from app.models import User
from app.auth import create_access_token

# Initialize FastMCP Server
mcp = FastMCP("StockAnalyzer")

API_URL = os.getenv("STOCK_ANALYZER_API_URL", "http://localhost:8000")

# Cache token and headers
_cached_headers = None

async def get_default_owner_id() -> int:
    async with async_session() as session:
        result = await session.execute(select(User).limit(1))
        user = result.scalar_one_or_none()
        if user:
            return user.id
        else:
            # Create a default user if none exists
            from app.auth import get_password_hash
            default_user = User(
                email="default@example.com",
                hashed_password=get_password_hash("password"),
                name="Default User"
            )
            session.add(default_user)
            await session.commit()
            await session.refresh(default_user)
            return default_user.id

async def get_auth_headers() -> dict:
    global _cached_headers
    if _cached_headers is not None:
        return _cached_headers
        
    owner_id = await get_default_owner_id()
    token = create_access_token(data={"sub": str(owner_id)})
    _cached_headers = {"Authorization": f"Bearer {token}"}
    return _cached_headers

# =====================================================================
# 1. Existing Analysis & Valuation Tools (REST Clients)
# =====================================================================

@mcp.tool()
async def query_stock_price(ticker: str) -> str:
    """Fetches the current stock price and change for a given ticker."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/stock/{ticker.upper()}")
        if r.status_code != 200:
            return f"Error: Failed to fetch stock data (status {r.status_code})"
        data = r.json()
        if "error" in data:
            return f"Error: {data['error']}"
        return (
            f"### Stock Price: {data['name']} ({data['ticker']})\n"
            f"- **Current Price:** ${data['price']:.2f}\n"
            f"- **Daily Change:** {data['change']:+,.2f} ({data['changePct']:+,.2f}%)\n"
            f"- **Volume:** {data['volume']:,}\n"
            f"- **Market Cap:** ${data['marketCap']:,.0f}"
        )

@mcp.tool()
async def get_company_profile(ticker: str) -> str:
    """Fetches company profile, sector, industry, and business summary."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/stock/{ticker.upper()}")
        if r.status_code != 200:
            return f"Error: Failed to fetch stock profile (status {r.status_code})"
        data = r.json()
        if "error" in data:
            return f"Error: {data['error']}"
        return (
            f"### Company Profile: {data['name']} ({data['ticker']})\n"
            f"- **Sector:** {data['sector']}\n"
            f"- **Industry:** {data['industry']}\n"
            f"- **52-Week Range:** ${data['fiftyTwoWeekLow']:.2f} - ${data['fiftyTwoWeekHigh']:.2f}\n\n"
            f"#### Business Summary\n"
            f"Please run a multi-agent chat query or generate a research report to get a detailed long summary."
        )

@mcp.tool()
async def get_financial_ratios(ticker: str) -> str:
    """Fetches key fundamental ratios (P/E ratio, market cap, and 52-week parameters)."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/stock/{ticker.upper()}")
        if r.status_code != 200:
            return f"Error: Failed to fetch financial ratios (status {r.status_code})"
        data = r.json()
        if "error" in data:
            return f"Error: {data['error']}"
        return (
            f"### Financial Highlights: {data['name']} ({data['ticker']})\n"
            f"- **Market Cap:** ${data['marketCap']:,.0f}\n"
            f"- **Trailing P/E Ratio:** {data['peRatio']}\n"
            f"- **52-Week High:** ${data['fiftyTwoWeekHigh']:.2f}\n"
            f"- **52-Week Low:** ${data['fiftyTwoWeekLow']:.2f}"
        )

@mcp.tool()
async def get_dcf_valuation(ticker: str) -> str:
    """Calculates intrinsic value of a company using the 5-Year DCF model."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/valuation/dcf/{ticker.upper()}")
        if r.status_code != 200:
            return f"Error: Failed to fetch DCF valuation (status {r.status_code})"
        data = r.json()
        if "error" in data:
            return f"Error: {data['error']}"
        return str(data.get("valuation", "No valuation result returned."))

@mcp.tool()
async def get_ddm_valuation(ticker: str) -> str:
    """Calculates intrinsic value using the Dividend Discount Model (Gordon Growth Model)."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/valuation/ddm/{ticker.upper()}")
        if r.status_code != 200:
            return f"Error: Failed to fetch DDM valuation (status {r.status_code})"
        data = r.json()
        if "error" in data:
            return f"Error: {data['error']}"
        return str(data.get("valuation", "No valuation result returned."))

@mcp.tool()
async def get_technical_indicators(ticker: str) -> str:
    """Calculates technical indicators for a stock (RSI, SMA, MACD, Bollinger Bands)."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/indicators/{ticker.upper()}?period=1y")
        if r.status_code != 200:
            return f"Error: Failed to fetch technical indicators (status {r.status_code})"
        data = r.json()
        if "error" in data:
            return f"Error: {data['error']}"
        
        indicators_list = data.get("indicators", [])
        if not indicators_list:
            return "No indicators history returned."
            
        latest = indicators_list[-1]
        return (
            f"### Technical Indicators: {ticker.upper()}\n"
            f"- **Date:** {latest.get('time')}\n"
            f"- **RSI (14):** {latest.get('rsi', 0.0):.2f} (Oversold < 30, Overbought > 70)\n"
            f"- **SMA (20):** {latest.get('sma20', 0.0):.2f}\n"
            f"- **SMA (50):** {latest.get('sma50', 0.0):.2f}\n"
            f"- **SMA (200):** {latest.get('sma200', 0.0):.2f}\n"
            f"- **EMA (20):** {latest.get('ema20', 0.0):.2f}\n"
            f"- **Bollinger Bands:** Upper: {latest.get('upper_band', 0.0):.2f} | Lower: {latest.get('lower_band', 0.0):.2f}\n"
            f"- **MACD Line:** {latest.get('macd', 0.0):.2f}\n"
            f"- **MACD Signal:** {latest.get('macd_signal', 0.0):.2f}\n"
            f"- **MACD Hist:** {latest.get('macd_hist', 0.0):.2f}"
        )

@mcp.tool()
async def get_risk_analysis(ticker: str) -> str:
    """Calculates risk metrics over the last year (volatility, Sharpe ratio, max drawdown)."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/stock/{ticker.upper()}/risk")
        if r.status_code != 200:
            return f"Error: Failed to fetch risk metrics (status {r.status_code})"
        data = r.json()
        if "error" in data:
            return f"Error: {data['error']}"
        return str(data.get("risk", "No risk analysis returned."))

@mcp.tool()
async def run_backtest(ticker: str, strategy: str = "sma_crossover", initial_capital: float = 10000.0, days: int = 365, stop_loss_pct: float = 0.0) -> str:
    """Backtests a simple trading strategy (e.g. 'sma_crossover', 'rsi_mean_reversion', 'macd_crossover', 'turtle_breakout')."""
    payload = {
        "ticker": ticker.upper(),
        "strategies": [strategy],
        "initial_capital": initial_capital,
        "days": days,
        "stop_loss_pct": stop_loss_pct
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_URL}/api/backtest", json=payload)
        if r.status_code != 200:
            return f"Error: Failed to run backtest (status {r.status_code})"
        data = r.json()
        if not data or "error" in data[0]:
            err = data[0].get("error", "Unknown backtest error") if data else "Unknown backtest error"
            return f"Error: {err}"
            
        bt = data[0]
        return (
            f"### Strategy Backtest Results: {bt.get('strategy').upper()} on {bt.get('ticker')}\n"
            f"- **Test Period:** {bt.get('period_days')} Days\n"
            f"- **Initial Capital:** ${bt.get('initial_capital'):,.2f}\n"
            f"- **Final Value:** ${bt.get('final_value'):,.2f}\n"
            f"- **Total Return:** {bt.get('total_return_pct'):+,.2f}%\n"
            f"- **Benchmark Return:** {bt.get('benchmark_return_pct'):+,.2f}%\n"
            f"- **Max Drawdown:** {bt.get('max_drawdown_pct'):.2f}%\n"
            f"- **Win Rate:** {bt.get('win_rate_pct'):.2f}%\n"
            f"- **Total Closed Trades:** {bt.get('total_trades')}"
        )

# =====================================================================
# 2. Qualitative & Narrative Tools (REST Clients)
# =====================================================================

@mcp.tool()
async def get_business_model_story(ticker: str) -> str:
    """Generates an AI fundamental narrative analysis of a company's business model story."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/fundamentals/{ticker.upper()}/story")
        if r.status_code != 200:
            return f"Error: Failed to fetch business model story (status {r.status_code})"
        data = r.json()
        return data.get("markdown", "No narrative returned.")

@mcp.tool()
async def get_porter_forces_analysis(ticker: str) -> str:
    """Generates a Porter's Five Forces qualitative industry competitiveness analysis."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/fundamentals/{ticker.upper()}/porter")
        if r.status_code != 200:
            return f"Error: Failed to fetch Porter's Five Forces analysis (status {r.status_code})"
        data = r.json()
        return data.get("markdown", "No narrative returned.")

@mcp.tool()
async def get_competitor_analysis(ticker: str) -> str:
    """Generates a qualitative and metrics-based competitor comparison report."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/fundamentals/{ticker.upper()}/competitors")
        if r.status_code != 200:
            return f"Error: Failed to fetch competitor comparison (status {r.status_code})"
        data = r.json()
        return data.get("markdown", "No narrative returned.")

@mcp.tool()
async def get_sec_mda_summary(ticker: str) -> str:
    """Extracts Item 7 (Management Discussion & Analysis) from the latest 10-K and summarizes it via Map-Reduce."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/filings/{ticker.upper()}/mda")
        if r.status_code != 200:
            return f"Error: Failed to fetch MD&A summary (status {r.status_code})"
        data = r.json()
        return data.get("markdown", "No narrative returned.")

@mcp.tool()
async def get_sec_risk_summary(ticker: str) -> str:
    """Extracts Item 1A (Risk Factors) from the latest 10-K and summarizes it via Map-Reduce."""
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_URL}/api/filings/{ticker.upper()}/risks")
        if r.status_code != 200:
            return f"Error: Failed to fetch risk summary (status {r.status_code})"
        data = r.json()
        return data.get("markdown", "No narrative returned.")

# =====================================================================
# 3. Database & Wealth Sync Tools (REST Clients)
# =====================================================================

@mcp.tool()
async def log_personal_expense(amount: float, category: str, description: str, date_str: Optional[str] = None, is_joint: bool = False) -> str:
    """Logs an expense transaction into the database via REST API."""
    headers = await get_auth_headers()
    
    if date_str:
        try:
            # Reformat to match JSON ISO format
            date_val = datetime.strptime(date_str, "%Y-%m-%d").isoformat()
        except ValueError:
            date_val = datetime.now().isoformat()
    else:
        date_val = datetime.now().isoformat()

    payload = {
        "date": date_val,
        "category": category,
        "amount": amount,
        "description": description,
        "is_joint": is_joint
    }

    async with httpx.AsyncClient() as client:
        r = await client.post(f"{API_URL}/api/finance/expenses", json=payload, headers=headers)
        if r.status_code != 200:
            return f"Error: Failed to log expense (status {r.status_code}): {r.text}"
        data = r.json()
        return f"Successfully logged expense of ${data['amount']:.2f} under '{data['category']}' (ID: {data['id']})"

@mcp.tool()
async def calculate_net_worth() -> str:
    """Aggregates all accounts, cash balances, manual assets, and stock portfolios to compute net worth in USD."""
    headers = await get_auth_headers()
    
    async with httpx.AsyncClient() as client:
        # Get net worth history (contains JIT calculated snapshot value for today)
        r_nw = await client.get(f"{API_URL}/api/finance/net-worth-history?resolution=daily", headers=headers)
        r_acc = await client.get(f"{API_URL}/api/finance/accounts", headers=headers)
        
        if r_nw.status_code != 200 or r_acc.status_code != 200:
            return "Error: Failed to fetch accounts or net worth data from API."
            
        nw_history = r_nw.json()
        accounts = r_acc.json()
        
        if not nw_history:
            return "No net worth snapshot generated."
            
        latest_snapshot = nw_history[-1]
        
        output = [
            "### 💼 Net Worth Aggregation Report (API-Driven)",
            f"**Total Assets:** ${latest_snapshot.get('total_assets', 0.0):,.2f}",
            f"**Total Liabilities:** ${latest_snapshot.get('total_liabilities', 0.0):,.2f}",
            f"**Net Worth:** **${latest_snapshot.get('net_worth', 0.0):,.2f}**",
            "",
            "#### Accounts Ledger Summary",
            "| Account Name | Classification | Class | Balance | Value (USD) |",
            "| :--- | :--- | :--- | :--- | :--- |"
        ]
        
        for a in accounts:
            classification = a.get("classification", "Asset").capitalize()
            ac_class = a.get("account_class", "Cash").capitalize()
            balance = a.get("balance", 0.0)
            balance_usd = a.get("balance_usd", balance)
            output.append(
                f"| {a.get('name')} | {classification} | {ac_class} | {a.get('currency')} {balance:,.2f} | ${balance_usd:,.2f} |"
            )
            
        return "\n".join(output)

@mcp.tool()
async def get_portfolio_holdings_report(portfolio_id: int = 1) -> str:
    """Generates an active holdings report, detailing weights, valuations, cost-basis, and unrealized gains."""
    headers = await get_auth_headers()
    
    async with httpx.AsyncClient() as client:
        # Fetch portfolio stats from API
        r = await client.get(f"{API_URL}/api/portfolio/{portfolio_id}", headers=headers)
        if r.status_code != 200:
            return f"Error: Failed to fetch portfolio holdings (status {r.status_code})"
        
        data = r.json()
        if "error" in data:
            return f"Error: {data['error']}"
            
        output = [
            f"### 📈 Portfolio Holdings Report: {data.get('name')}",
            f"**Total Cost Basis:** {data.get('currency')} {data.get('total_cost', 0.0):,.2f}",
            f"**Current Market Value:** {data.get('currency')} {data.get('total_value', 0.0):,.2f}",
            f"**Total Unrealized Return:** {data.get('currency')} {data.get('total_pnl', 0.0):+,.2f} ({data.get('total_pnl_pct', 0.0):+,.2f}%)",
            "",
            "| Ticker | Name | Shares | Avg Cost | Price | Current Value | Weight | Return |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        
        for h in data.get("holdings", []):
            weight = h.get("weight_pct", 0.0)
            pnl_sign = "+" if h.get("unrealized_pnl", 0.0) >= 0 else ""
            output.append(
                f"| **{h.get('ticker')}** | {h.get('name')} | {h.get('shares'):.4f} | {h.get('avg_cost_basis'):.2f} | {h.get('current_price'):.2f} | {h.get('current_value'):.2f} | {weight:.1f}% | {pnl_sign}{h.get('unrealized_pnl'):.2f} ({pnl_sign}{h.get('unrealized_pnl_pct'):.1f}%) |"
            )
            
        return "\n".join(output)

# =====================================================================
# 4. Multi-Agent Gateway & Obsidian Workflow note creation
# =====================================================================

@mcp.tool()
async def ask_financial_analyst(message: str) -> str:
    """Submits a stock query directly to the LangGraph Multi-Agent system and returns its final answer."""
    payload = {
        "message": message,
        "thread_id": "mcp-oab-thread"
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{API_URL}/api/chat", json=payload)
        if r.status_code != 200:
            return f"Error: LangGraph agent chat failed (status {r.status_code})"
        return r.json().get("reply", "No response returned.")

@mcp.tool()
async def generate_stock_research_note(ticker: str, vault_path: str) -> str:
    """
    Runs multi-agent stock analyses via API and writes a consolidated research report note 
    at '/Investments/Research/{TICKER}.md' inside the Obsidian vault.
    """
    ticker_upper = ticker.upper().strip()
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Fetch valuations and qualitative reports from API endpoints
        price_task = client.get(f"{API_URL}/api/stock/{ticker_upper}")
        dcf_task = client.get(f"{API_URL}/api/valuation/dcf/{ticker_upper}")
        story_task = client.get(f"{API_URL}/api/fundamentals/{ticker_upper}/story")
        porter_task = client.get(f"{API_URL}/api/fundamentals/{ticker_upper}/porter")
        competitors_task = client.get(f"{API_URL}/api/fundamentals/{ticker_upper}/competitors")
        mda_task = client.get(f"{API_URL}/api/filings/{ticker_upper}/mda")
        risk_task = client.get(f"{API_URL}/api/filings/{ticker_upper}/risks")
        
        results = await asyncio.gather(
            price_task, dcf_task, story_task, porter_task,
            competitors_task, mda_task, risk_task,
            return_exceptions=True
        )

        def get_value(idx, key, default=""):
            r = results[idx]
            if isinstance(r, Exception) or r.status_code != 200:
                return f"Analysis section unavailable: {r}"
            return r.json().get(key, default)

        name = get_value(0, "name", ticker_upper)
        price = get_value(0, "price", "N/A")
        sector = get_value(0, "sector", "Unknown")
        industry = get_value(0, "industry", "Unknown")
        summary = get_value(0, "longBusinessSummary", "Summary pending.")
        
        dcf = get_value(1, "valuation", "DCF valuation pending.")
        story = get_value(2, "markdown", "Story narrative pending.")
        porter = get_value(3, "markdown", "Porter's analysis pending.")
        competitors = get_value(4, "markdown", "Competitor analysis pending.")
        mda = get_value(5, "markdown", "MD&A summary pending.")
        sec_risk = get_value(6, "markdown", "SEC risk factors summary pending.")

        markdown_content = f"""# 📈 Stock Research Report: {name} ({ticker_upper})

Created: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Current Price: **${price}**
Sector: *{sector}* | Industry: *{industry}*

## 🏢 Business Overview
{summary}

---

## 💵 Valuation & Intrinsic Value Analysis
{dcf}

---

## 📖 Business Narrative & Moat Story
{story}

---

## 🛡️ Porter's Five Forces
{porter}

---

## 👥 Competitor Comparison
{competitors}

---

## 📝 SEC Filing Summaries (Map-Reduce Insights)

### Management's Discussion and Analysis (MD&A - Item 7)
{mda}

### Top Risk Factors (Item 1A)
{sec_risk}
"""

        investments_dir = os.path.join(os.path.expanduser(vault_path), "Investments", "Research")
        os.makedirs(investments_dir, exist_ok=True)
        
        note_path = os.path.join(investments_dir, f"{ticker_upper}.md")
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
            
        return f"Successfully created stock research report for [[{ticker_upper}]] at: {note_path}"

@mcp.tool()
async def sync_portfolio_dashboard(vault_path: str) -> str:
    """
    Consolidates holdings and net worth aggregates from database APIs and writes 
    an updated dashboard at '/Investments/Portfolio Dashboard.md' in the Obsidian vault.
    """
    net_worth_report = await calculate_net_worth()
    holdings_report = await get_portfolio_holdings_report()
    
    dashboard_content = f"""# 💼 Wealth & Portfolio Dashboard

Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 📊 Net Worth Aggregation
{net_worth_report}

---

## 📈 Active Portfolios Summary
{holdings_report}

---

## 🛠️ Quick Actions
- [ ] Log expense $0.00 for description #agent
- [ ] Generate a stock research note for AAPL #agent
- [ ] Update my portfolio dashboard #agent
"""

    investments_dir = os.path.join(os.path.expanduser(vault_path), "Investments")
    os.makedirs(investments_dir, exist_ok=True)
    
    dashboard_path = os.path.join(investments_dir, "Portfolio Dashboard.md")
    with open(dashboard_path, "w", encoding="utf-8") as f:
        f.write(dashboard_content)
        
    return f"Successfully synced portfolio dashboard inside vault at: {dashboard_path}"


if __name__ == "__main__":
    mcp.run()
