import os
import asyncio
import logging
from typing import Dict, Any, List

import yfinance as yf
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
import agentmail

from sqlalchemy.ext.asyncio import AsyncSession
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

async def gather_monthly_summary_context(db: AsyncSession, user_id: int, month: str) -> Dict[str, Any]:
    """Gather monthly financial summary context for a user in INR terms."""
    import datetime
    from sqlalchemy import select, and_
    from app.models import Expense, LinkedAccount, FinancialGoal, GoalContribution, PortfolioHolding, ManualAsset, Account, NetWorthSnapshot, User
    from app.cache import get_live_price, get_cache
    from api.routes.finance import convert_currency, capture_user_net_worth_snapshot

    # Parse month YYYY-MM
    try:
        year, m = map(int, month.split('-'))
        start_date = datetime.datetime(year, m, 1, tzinfo=datetime.timezone.utc)
        if m == 12:
            end_date = datetime.datetime(year + 1, 1, 1, tzinfo=datetime.timezone.utc)
        else:
            end_date = datetime.datetime(year, m + 1, 1, tzinfo=datetime.timezone.utc)
    except ValueError:
        logger.error(f"Invalid month format: {month}. Expected YYYY-MM.")
        raise ValueError("Invalid month format, expected YYYY-MM")

    # Fetch linked partner user IDs
    links = await db.execute(select(LinkedAccount.linked_user_id).where(LinkedAccount.user_id == user_id))
    linked_ids = [r[0] for r in links.all()]
    all_user_ids = [user_id] + linked_ids

    # User mapping for names
    users_res = await db.execute(select(User).where(User.id.in_(all_user_ids)))
    user_map = {u.id: (u.name or u.email.split('@')[0]) for u in users_res.scalars().all()}

    # 1. Fetch Expenses
    expense_query = select(Expense).where(
        and_(
            Expense.owner_id.in_(all_user_ids),
            Expense.date >= start_date,
            Expense.date < end_date
        )
    )
    result = await db.execute(expense_query.order_by(Expense.date.desc()))
    expenses = result.scalars().all()

    total_expenses = sum(e.amount for e in expenses)
    expenses_by_category = {}
    for e in expenses:
        expenses_by_category[e.category] = expenses_by_category.get(e.category, 0.0) + e.amount

    expenses_by_category_pct = {}
    for cat, amt in expenses_by_category.items():
        expenses_by_category_pct[cat] = (amt / total_expenses * 100) if total_expenses > 0 else 0.0

    # Top 5 expenses by amount
    sorted_expenses = sorted(expenses, key=lambda x: x.amount, reverse=True)
    top_5_expenses = []
    for e in sorted_expenses[:5]:
        payer_name = user_map.get(e.owner_id, "Unknown")
        top_5_expenses.append({
            "date": e.date.strftime("%Y-%m-%d"),
            "category": e.category,
            "amount": e.amount,
            "pct": (e.amount / total_expenses * 100) if total_expenses > 0 else 0.0,
            "description": e.description or "",
            "is_joint": bool(e.is_joint),
            "payer": payer_name
        })

    # 2. Fetch Goals and contributions up to end_date
    goals_res = await db.execute(
        select(FinancialGoal)
        .where(FinancialGoal.owner_id.in_(all_user_ids))
        .order_by(FinancialGoal.created_at.desc())
    )
    goals = goals_res.scalars().all()

    goals_summary = []
    for goal in goals:
        contribs_res = await db.execute(
            select(GoalContribution)
            .where(
                and_(
                    GoalContribution.goal_id == goal.id,
                    GoalContribution.date < end_date
                )
            )
        )
        contribs = contribs_res.scalars().all()
        total_manual_saved = sum(c.amount for c in contribs)

        # Linked asset value
        linked_asset_value = 0.0
        if goal.linked_asset_type == "portfolio" and goal.linked_asset_id:
            holdings_res = await db.execute(
                select(PortfolioHolding)
                .where(PortfolioHolding.portfolio_id == goal.linked_asset_id)
            )
            holdings = holdings_res.scalars().all()
            portfolio_val_usd = 0.0
            for h in holdings:
                price = await get_live_price(h.ticker, fallback=h.avg_cost_basis)
                ticker_currency = (await get_cache(f"currency:{h.ticker}")) or "USD"
                price_usd = await convert_currency(price, ticker_currency, "USD")
                portfolio_val_usd += h.shares * price_usd
            linked_asset_value = portfolio_val_usd
        elif goal.linked_asset_type == "manual_asset" and goal.linked_asset_id:
            asset_res = await db.execute(
                select(ManualAsset)
                .where(ManualAsset.id == goal.linked_asset_id)
            )
            asset = asset_res.scalar_one_or_none()
            if asset:
                linked_asset_value = asset.value
        elif goal.linked_asset_type == "account" and goal.linked_asset_id:
            account_res = await db.execute(
                select(Account)
                .where(Account.id == goal.linked_asset_id)
            )
            account = account_res.scalar_one_or_none()
            if account:
                linked_asset_value = await convert_currency(account.balance, account.currency, "USD")

        # Convert goal targets and total_saved to INR
        total_saved_inr = await convert_currency(total_manual_saved + linked_asset_value, "USD", "INR")
        target_amount_inr = await convert_currency(goal.target_amount, "USD", "INR")
        progress_percent = min((total_saved_inr / target_amount_inr) * 100, 100.0) if target_amount_inr > 0 else 0.0

        goals_summary.append({
            "title": goal.title,
            "category": goal.category,
            "target_amount": target_amount_inr,
            "target_date": goal.target_date.strftime("%Y-%m-%d"),
            "total_saved": total_saved_inr,
            "progress_percent": progress_percent,
            "linked_asset_type": goal.linked_asset_type
        })

    # 3. Fetch Net Worth snapshots
    # Snapshot for this month
    curr_snapshot_res = await db.execute(
        select(NetWorthSnapshot)
        .where(
            and_(
                NetWorthSnapshot.owner_id == user_id,
                NetWorthSnapshot.date >= start_date,
                NetWorthSnapshot.date < end_date
            )
        )
        .order_by(NetWorthSnapshot.date.desc())
        .limit(1)
    )
    curr_snapshot = curr_snapshot_res.scalar_one_or_none()

    # Capture live snapshot if missing and this is the current month
    today = datetime.datetime.now(datetime.timezone.utc)
    if not curr_snapshot and year == today.year and m == today.month:
        try:
            curr_snapshot = await capture_user_net_worth_snapshot(db, user_id, today)
        except Exception as e:
            logger.error(f"Failed to capture live snapshot for user {user_id}: {e}")

    # Previous month's snapshot
    prev_snapshot_res = await db.execute(
        select(NetWorthSnapshot)
        .where(
            and_(
                NetWorthSnapshot.owner_id == user_id,
                NetWorthSnapshot.date < start_date
            )
        )
        .order_by(NetWorthSnapshot.date.desc())
        .limit(1)
    )
    prev_snapshot = prev_snapshot_res.scalar_one_or_none()

    # Convert everything to INR (snapshots are in USD)
    current_assets = curr_snapshot.total_assets if curr_snapshot else 0.0
    current_liabilities = curr_snapshot.total_liabilities if curr_snapshot else 0.0
    
    current_assets_inr = await convert_currency(current_assets, "USD", "INR")
    current_liabilities_inr = await convert_currency(current_liabilities, "USD", "INR")
    current_nw_inr = current_assets_inr - current_liabilities_inr

    prev_assets = prev_snapshot.total_assets if prev_snapshot else 0.0
    prev_liabilities = prev_snapshot.total_liabilities if prev_snapshot else 0.0

    prev_assets_inr = await convert_currency(prev_assets, "USD", "INR")
    prev_liabilities_inr = await convert_currency(prev_liabilities, "USD", "INR")
    prev_nw_inr = prev_assets_inr - prev_liabilities_inr

    nw_change_inr = current_nw_inr - prev_nw_inr
    nw_change_pct = (nw_change_inr / prev_nw_inr * 100) if prev_nw_inr != 0 else 0.0

    # 4. Detailed Accounts breakdown
    accounts_res = await db.execute(select(Account).where(Account.owner_id.in_(all_user_ids)))
    accounts = accounts_res.scalars().all()
    
    accounts_summary = []
    for a in accounts:
        balance = a.balance
        usd_bal = None
        if a.account_class == "portfolio":
            port_res_acc = await db.execute(select(Portfolio).where(Portfolio.account_id == a.id))
            portfolios_acc = port_res_acc.scalars().all()
            if portfolios_acc:
                port_ids = [p.id for p in portfolios_acc]
                holdings_res = await db.execute(select(PortfolioHolding).where(PortfolioHolding.portfolio_id.in_(port_ids)))
                holdings = holdings_res.scalars().all()
                portfolio_val_usd = 0.0
                for h in holdings:
                    price = await get_live_price(h.ticker, fallback=h.avg_cost_basis)
                    ticker_currency = (await get_cache(f"currency:{h.ticker}")) or "USD"
                    price_usd = await convert_currency(price, ticker_currency, "USD")
                    portfolio_val_usd += h.shares * price_usd
                balance = await convert_currency(portfolio_val_usd, "USD", a.currency)
                usd_bal = portfolio_val_usd

        if usd_bal is None:
            usd_bal = await convert_currency(balance, a.currency, "USD")
        
        balance_inr = await convert_currency(usd_bal, "USD", "INR")
        
        accounts_summary.append({
            "name": a.name,
            "classification": a.classification,
            "account_class": a.account_class,
            "balance": balance,
            "currency": a.currency,
            "balance_inr": balance_inr
        })

    # 5. Detailed Portfolios breakdown
    portfolios_res = await db.execute(select(Portfolio).where(Portfolio.owner_id.in_(all_user_ids)))
    portfolios = portfolios_res.scalars().all()
    
    portfolios_summary = []
    for p in portfolios:
        holdings_res = await db.execute(select(PortfolioHolding).where(PortfolioHolding.portfolio_id == p.id))
        holdings = holdings_res.scalars().all()
        
        holdings_list = []
        portfolio_val_usd = 0.0
        for h in holdings:
            price = await get_live_price(h.ticker, fallback=h.avg_cost_basis)
            ticker_currency = (await get_cache(f"currency:{h.ticker}")) or "USD"
            price_usd = await convert_currency(price, ticker_currency, "USD")
            value_usd = h.shares * price_usd
            portfolio_val_usd += value_usd
            
            value_inr = await convert_currency(value_usd, "USD", "INR")
            holdings_list.append({
                "ticker": h.ticker,
                "shares": h.shares,
                "avg_cost_basis": h.avg_cost_basis,
                "current_price": price,
                "value_inr": value_inr
            })
            
        portfolio_val_inr = await convert_currency(portfolio_val_usd, "USD", "INR")
        portfolios_summary.append({
            "name": p.name,
            "total_value_inr": portfolio_val_inr,
            "holdings": holdings_list
        })
        
    # 6. Fetch Manual Assets
    manual_assets_res = await db.execute(select(ManualAsset).where(ManualAsset.owner_id.in_(all_user_ids)))
    manual_assets = manual_assets_res.scalars().all()
    
    manual_assets_summary = []
    for ma in manual_assets:
        value_inr = await convert_currency(ma.value, "USD", "INR")
        manual_assets_summary.append({
            "asset_type": ma.asset_type,
            "value_inr": value_inr,
            "description": ma.description or ""
        })

    return {
        "month": month,
        "expenses": {
            "total": total_expenses,
            "by_category": expenses_by_category,
            "by_category_pct": expenses_by_category_pct,
            "top_5": top_5_expenses
        },
        "net_worth": {
            "current": {
                "total_assets": current_assets_inr,
                "total_liabilities": current_liabilities_inr,
                "net_worth": current_nw_inr,
                "date": curr_snapshot.date.strftime("%Y-%m-%d") if curr_snapshot else None
            },
            "previous": {
                "total_assets": prev_assets_inr,
                "total_liabilities": prev_liabilities_inr,
                "net_worth": prev_nw_inr,
                "date": prev_snapshot.date.strftime("%Y-%m-%d") if prev_snapshot else None
            },
            "change": {
                "net_worth": nw_change_inr,
                "pct": nw_change_pct
            }
        },
        "goals": goals_summary,
        "accounts": accounts_summary,
        "portfolios": portfolios_summary,
        "manual_assets": manual_assets_summary
    }

async def generate_monthly_summary_email_content(user_name: str, month: str, context: Dict[str, Any]) -> str:
    """Generates the HTML monthly summary email content using Gemini."""
    # Format categories
    categories_str = "\n".join([f"- {cat}: {context['expenses']['by_category'][cat]:,.2f} ({pct:.1f}%)" for cat, pct in context["expenses"]["by_category_pct"].items()])
    
    # Format top expenses
    top_str = "\n".join([f"- {e['date']}: {e['payer']} paid {e['amount']:,.2f} ({e['pct']:.1f}%) for {e['description']} ({e['category']})" for e in context["expenses"]["top_5"]])
    
    # Format goals
    goals_str = "\n".join([f"- {g['title']} ({g['category']}): Saved INR {g['total_saved']:,.2f} of INR {g['target_amount']:,.2f} ({g['progress_percent']:.1f}%) - Target: {g['target_date']}" for g in context["goals"]])

    # Format accounts breakdown
    accounts_str = ""
    for a in context["accounts"]:
        classification_title = "Asset" if a["classification"] == "asset" else "Liability"
        accounts_str += f"- {a['name']} ({classification_title} / {a['account_class']}): Native: {a['balance']:,.2f} {a['currency']} | Converted: INR {a['balance_inr']:,.2f}\n"

    # Format portfolios breakdown
    portfolios_str = ""
    for p in context["portfolios"]:
        portfolios_str += f"- Portfolio: {p['name']} (Total Value: INR {p['total_value_inr']:,.2f})\n"
        for h in p["holdings"]:
            portfolios_str += f"  * {h['ticker']}: {h['shares']} shares | Avg Cost: {h['avg_cost_basis']:.2f} | Current Price: {h['current_price']:.2f} | Total Value: INR {h['value_inr']:,.2f}\n"

    # Format manual assets breakdown
    manual_assets_str = ""
    for ma in context["manual_assets"]:
        desc = f" ({ma['description']})" if ma['description'] else ""
        manual_assets_str += f"- {ma['asset_type']}{desc}: INR {ma['value_inr']:,.2f}\n"

    prompt = f"""You are an expert financial analyst. Please write a highly professional, beautifully formatted HTML monthly financial summary email for {user_name} for the month of {month}.

Net Worth figures must be analyzed and displayed in Indian Rupee (INR) terms (using the ₹ symbol or "INR" prefix).
Expense figures are raw values in the user's current currency configuration, and must NOT be converted to INR.

Financial Data for the Month:
- Total Expenses: {context['expenses']['total']:,.2f}

Net Worth Snapshot (in INR):
- Current Assets: INR {context['net_worth']['current']['total_assets']:,.2f}
- Current Liabilities: INR {context['net_worth']['current']['total_liabilities']:,.2f}
- Current Net Worth: INR {context['net_worth']['current']['net_worth']:,.2f}
- MoM Net Worth Change: INR {context['net_worth']['change']['net_worth']:,.2f} ({context['net_worth']['change']['pct']:.1f}%)

Expenses by Category (Absolute and % of Total):
{categories_str}

Top 5 Expenses:
{top_str}

Detailed Accounts List:
{accounts_str}

Detailed Portfolios and Holdings List:
{portfolios_str}

Detailed Manual Assets List:
{manual_assets_str}

Financial Goals Progress:
{goals_str}

Requirements for the HTML Email:
1. Provide a professional, engaging summary of the user's financial performance this month.
2. Deliver expert, actionable insights on their expenses. You MUST analyze and comment on their expenses strictly in percentage/proportion terms (e.g., proportion of overall monthly expenditure) using the raw/current expense values provided, identifying high-proportion categories. Do not convert expense numbers to INR.
3. Deliver a detailed analysis of the existing set of accounts (assets vs liabilities) and portfolios (including stock holdings) and their individual contributions and percentage weight to the total net worth in INR terms.
4. Review the progress towards their financial goals in INR terms, giving encouraging feedback.
5. Do NOT include any references, mentions, or calculations relating to income, salary, or savings rates, as the user is intentionally not recording income.
6. Format the output directly as valid HTML that is clean, responsive, and uses inline CSS for styling. Use a modern, premium dark-mode or cohesive glassmorphic aesthetic matching a top-tier fintech app.
7. Return purely the HTML string, with no markdown code blocks wrapping it. Do not include ```html.
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

async def send_monthly_summary_email(to_email: str, subject: str, html_content: str) -> bool:
    """Sends the monthly summary HTML content via agentmail."""
    if not AGENTMAIL_API_KEY or not AGENTMAIL_INBOX_ID or not RECIPIENT_EMAIL:
        logger.warning("Missing required environment variables for AgentMail (AGENTMAIL_API_KEY, AGENTMAIL_INBOX_ID, RECIPIENT_EMAIL). Attempting send to dynamic email, but config might fail.")
    
    recipient = RECIPIENT_EMAIL or to_email
    if not recipient:
        logger.error("No recipient email address available to send the summary.")
        return False
        
    try:
        from agentmail import AgentMail
        client = AgentMail(api_key=AGENTMAIL_API_KEY or "dummy_key")
        
        response = client.inboxes.messages.send(
            inbox_id=AGENTMAIL_INBOX_ID or "dummy_inbox",
            to=[recipient],
            subject=subject,
            html=html_content
        )
        logger.info(f"Monthly summary email sent successfully using AgentMail. Message ID: {response.message_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send monthly summary email via AgentMail: {e}")
        return False

async def run_monthly_summary_job(db: AsyncSession, user_id: int, month: str | None = None) -> bool:
    """Coordinates gathering context, generating summary, and sending the email."""
    from app.models import User
    user = await db.get(User, user_id)
    if not user:
        logger.error(f"User {user_id} not found.")
        return False

    if not month:
        # Default to previous month
        import datetime
        today = datetime.date.today()
        # Calculate first day of current month, then subtract 1 day to get into previous month
        first_day_curr = today.replace(day=1)
        prev_month_date = first_day_curr - datetime.timedelta(days=1)
        month = prev_month_date.strftime("%Y-%m")

    logger.info(f"Starting monthly summary job for user {user.email} for month {month}...")
    try:
        context = await gather_monthly_summary_context(db, user_id, month)
        user_name = user.name or user.email.split('@')[0]
        html_content = await generate_monthly_summary_email_content(user_name, month, context)
        subject = f"📊 Monthly Financial Summary — {month}"
        success = await send_monthly_summary_email(user.email, subject, html_content)
        return success
    except Exception as e:
        logger.error(f"Failed monthly summary job: {e}")
        return False
