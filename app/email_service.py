import os
import asyncio
import logging
from typing import Dict, Any, List

import yfinance as yf
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import agentmail

from app.database import async_session
from app.models import Portfolio, PortfolioHolding
from app.llm import get_llm
from ddgs import DDGS

logger = logging.getLogger(__name__)

# Constants
AGENTMAIL_API_KEY = os.getenv("AGENTMAIL_API_KEY")
AGENTMAIL_INBOX_ID = os.getenv("AGENTMAIL_INBOX_ID")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

async def gather_portfolio_context(portfolio_id: int = 1) -> Dict[str, Any]:
    """Gather holdings, live prices, and recent news for the portfolio."""
    context = {"holdings": [], "news": {}, "macro": "The broader market has been volatile recently due to inflation data and Fed rate commentary."}
    
    async with async_session() as session:
        port = await session.get(Portfolio, portfolio_id)
        if not port:
            logger.error(f"Portfolio {portfolio_id} not found.")
            return context

        from sqlalchemy import select
        result = await session.execute(
            select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio_id)
        )
        holdings = result.scalars().all()

    if not holdings:
        return context

    # We will gather info concurrently to save time
    async def fetch_ticker_data(h: PortfolioHolding):
        try:
            # Price
            def _fetch_info():
                return yf.Ticker(h.ticker).info
            
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                info = await loop.run_in_executor(pool, _fetch_info)
                
            current_price = (
                info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose") or 0
            )
            
            holding_data = {
                "ticker": h.ticker,
                "shares": h.shares,
                "avg_cost_basis": h.avg_cost_basis,
                "current_price": current_price,
                "unrealized_pnl_pct": ((current_price - h.avg_cost_basis) / h.avg_cost_basis * 100) if h.avg_cost_basis else 0
            }
            
            # News
            def _fetch_news():
                results = DDGS().news(f"{h.ticker} stock news", max_results=3)
                if not results: return []
                return [f"{item.get('title')}: {item.get('body')}" for item in results]
                
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                news_items = await loop.run_in_executor(pool, _fetch_news)
                
            return holding_data, news_items
            
        except Exception as e:
            logger.error(f"Error fetching data for {h.ticker}: {e}")
            return None, []

    tasks = [fetch_ticker_data(h) for h in holdings]
    results = await asyncio.gather(*tasks)

    for res in results:
        if res and res[0]:
            h_data, h_news = res
            context["holdings"].append(h_data)
            context["news"][h_data["ticker"]] = h_news

    return context


async def generate_daily_email_content(context: Dict[str, Any]) -> str:
    """Generates the HTML email content using Gemini."""
    if not context.get("holdings"):
        return "<p>Your portfolio is currently empty. Add holdings to receive daily analysis.</p>"

    # Format context for the LLM
    holdings_str = "\n".join([f"- {h['ticker']}: {h['shares']} shares @ ${h['avg_cost_basis']:.2f} (Current: ${h['current_price']:.2f}, PnL: {h['unrealized_pnl_pct']:.2f}%)" for h in context["holdings"]])
    news_str = ""
    for ticker, news in context["news"].items():
        if news:
            news_str += f"\n**{ticker} News:**\n" + "\n".join([f"  - {n}" for n in news])
            
    prompt = f"""You are an expert financial analyst. Please write a highly professional, beautifully formatted HTML newsletter for my daily stock portfolio update.

Portfolio Holdings:
{holdings_str}

Recent News for Holdings:
{news_str}

General Macro Context:
{context['macro']}

Requirements for the HTML Email:
1. Provide a professional, engaging summary of the daily news impacts on the specific portfolio.
2. Include expert commentary on the portfolio composition and actionable insights (e.g., rebalancing, risk management).
3. Provide a brief macro overview on how broader market moves might impact these specific holdings.
4. Mention any stocks that might be reaching important technical zones or have upcoming earnings.
5. Format the output directly as valid HTML that is clean, responsive, and uses inline CSS for styling. Use a modern, sleek aesthetic suitable for a premium financial report.
6. Return purely the HTML string, with no markdown code blocks wrapping it. Do not include ```html.
"""

    llm = get_llm(temperature=0.4)
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content.strip()
    
    # Strip markdown formatting if the model still includes it
    if content.startswith("```html"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
        
    return content.strip()

async def send_portfolio_email(html_content: str):
    """Sends the HTML content via agentmail."""
    if not AGENTMAIL_API_KEY or not AGENTMAIL_INBOX_ID or not RECIPIENT_EMAIL:
        logger.error("Missing required environment variables for AgentMail (AGENTMAIL_API_KEY, AGENTMAIL_INBOX_ID, RECIPIENT_EMAIL).")
        return False
        
    try:
        from agentmail import AgentMail
        client = AgentMail(api_key=AGENTMAIL_API_KEY)
        
        response = client.inboxes.messages.send(
            inbox_id=AGENTMAIL_INBOX_ID,
            to=[RECIPIENT_EMAIL],
            subject="📈 Daily Portfolio Analyst Update",
            html=html_content
        )
        logger.info(f"Email sent successfully using AgentMail. Message ID: {response.message_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email via AgentMail: {e}")
        return False

async def run_daily_job():
    """Main entry point for the daily job."""
    logger.info("Starting daily portfolio email job...")
    
    # Defaulting to portfolio ID 1 for now (the "My Portfolio" default)
    context = await gather_portfolio_context(portfolio_id=1)
    
    logger.info("Context gathered. Generating AI analysis...")
    html_content = await generate_daily_email_content(context)
    
    logger.info("Analysis generated. Sending email...")
    success = await send_portfolio_email(html_content)
    
    if success:
        logger.info("Daily portfolio email job completed successfully.")
    else:
        logger.error("Daily portfolio email job failed during send.")
