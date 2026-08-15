import asyncio
import concurrent.futures
from datetime import datetime, timedelta
from typing import Annotated
import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy import select, delete, func as sqlfunc
from app.database import async_session
from app.models import User, Portfolio, PortfolioHolding, Account, Transaction
from api.routes.auth import get_current_user
from api.routes.finance import convert_currency
from app.cache import get_cache, set_cache, get_live_price

router = APIRouter(prefix="/api", tags=["portfolio"])

class HoldingRequest(BaseModel):
    ticker: str
    shares: float
    avg_cost_basis: float

class PortfolioUpdate(BaseModel):
    name: str | None = None
    account_id: int | None = None

class PortfolioCreate(BaseModel):
    name: str
    account_id: int | None = None

@router.get("/portfolio")
async def list_portfolios(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """List all portfolios for the current user. Creates a default one if none exist."""
    async with async_session() as session:
        result = await session.execute(
            select(Portfolio).where(Portfolio.owner_id == current_user.id).order_by(Portfolio.id)
        )
        portfolios = result.scalars().all()

        if not portfolios:
            default = Portfolio(name="My Portfolio", owner_id=current_user.id)
            session.add(default)
            await session.commit()
            await session.refresh(default)
            portfolios = [default]

        response = []
        for p in portfolios:
            account_name = None
            if p.account_id:
                acc = await session.get(Account, p.account_id)
                if acc:
                    account_name = acc.name
            
            response.append({
                "id": p.id,
                "name": p.name,
                "account_id": p.account_id,
                "account_name": account_name,
                "created_at": str(p.created_at)
            })
        return response

@router.post("/portfolio")
async def create_portfolio(
    port_in: PortfolioCreate,
    current_user: Annotated[User, Depends(get_current_user)]
):
    async with async_session() as session:
        if port_in.account_id is not None:
            acc = await session.get(Account, port_in.account_id)
            if not acc or acc.owner_id != current_user.id:
                raise HTTPException(status_code=400, detail="Invalid account ID")
                
        portfolio = Portfolio(
            name=port_in.name,
            owner_id=current_user.id,
            account_id=port_in.account_id
        )
        session.add(portfolio)
        await session.commit()
        await session.refresh(portfolio)
        return {
            "id": portfolio.id,
            "name": portfolio.name,
            "account_id": portfolio.account_id,
            "created_at": str(portfolio.created_at)
        }

@router.patch("/portfolio/{portfolio_id}")
async def update_portfolio(
    portfolio_id: int,
    port_in: PortfolioUpdate,
    current_user: Annotated[User, Depends(get_current_user)]
):
    async with async_session() as session:
        port = await session.get(Portfolio, portfolio_id)
        if not port or port.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Portfolio not found")
            
        if port_in.name is not None:
            port.name = port_in.name
            
        if port_in.account_id is not None:
            if port_in.account_id == -1: # Sentinel for unlinking
                port.account_id = None
            else:
                acc = await session.get(Account, port_in.account_id)
                if not acc or acc.owner_id != current_user.id:
                    raise HTTPException(status_code=400, detail="Invalid account ID")
                port.account_id = port_in.account_id
                
        await session.commit()
        return {"status": "success"}

@router.delete("/portfolio/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)]
):
    async with async_session() as session:
        port = await session.get(Portfolio, portfolio_id)
        if not port or port.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Portfolio not found")
            
        await session.delete(port)
        await session.commit()
        return {"status": "success"}

@router.get("/portfolio/{portfolio_id}")
async def get_portfolio(portfolio_id: int):
    """Get a portfolio with all holdings, enriched with live prices."""
    async with async_session() as session:
        port = await session.get(Portfolio, portfolio_id)
        if not port:
            return {"error": f"Portfolio {portfolio_id} not found"}

        target_currency = "USD"
        if port.account_id:
            acc = await session.get(Account, port.account_id)
            if acc:
                target_currency = acc.currency or "USD"

        result = await session.execute(
            select(PortfolioHolding)
            .where(PortfolioHolding.portfolio_id == portfolio_id)
            .order_by(PortfolioHolding.added_at)
        )
        holdings = result.scalars().all()

        enriched = []
        total_value = 0.0
        total_cost = 0.0

        for h in holdings:
            current_price = await get_live_price(h.ticker, fallback=0.0)

            sector = await get_cache(f"sector:{h.ticker}") or "Unknown"
            name = await get_cache(f"name:{h.ticker}") or h.ticker
            ticker_currency = (await get_cache(f"currency:{h.ticker}")) or "USD"

            converted_current_price = await convert_currency(current_price, ticker_currency, target_currency)
            converted_avg_cost_basis = await convert_currency(h.avg_cost_basis, ticker_currency, target_currency)

            current_value = h.shares * converted_current_price
            cost_basis_total = h.shares * converted_avg_cost_basis
            unrealized_pnl = current_value - cost_basis_total
            unrealized_pnl_pct = (unrealized_pnl / cost_basis_total * 100) if cost_basis_total > 0 else 0

            total_value += current_value
            total_cost += cost_basis_total

            enriched.append({
                "id": h.id,
                "ticker": h.ticker,
                "name": name,
                "sector": sector,
                "shares": h.shares,
                "avg_cost_basis": round(converted_avg_cost_basis, 2),
                "current_price": round(converted_current_price, 2),
                "current_value": round(current_value, 2),
                "cost_basis_total": round(cost_basis_total, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
            })

        for item in enriched:
            item["weight_pct"] = round((item["current_value"] / total_value * 100) if total_value > 0 else 0, 2)

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        last_txn_result = await session.execute(
            select(Transaction.executed_at)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at.desc())
            .limit(1)
        )
        last_txn_date = last_txn_result.scalar()

        account_name = None
        if port.account_id:
            acc = await session.get(Account, port.account_id)
            if acc:
                account_name = acc.name

        return {
            "id": port.id,
            "name": port.name,
            "account_id": port.account_id,
            "account_name": account_name,
            "currency": target_currency,
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "num_holdings": len(enriched),
            "last_updated": str(last_txn_date)[:10] if last_txn_date else None,
            "holdings": enriched,
        }

@router.get("/portfolio/{portfolio_id}/benchmarks")
async def get_portfolio_benchmarks(portfolio_id: int):
    """Compute portfolio % returns vs S&P 500 / NASDAQ, plus beta, alpha, Sharpe.
    Uses Time-Weighted Return (TWR) for daily performance, accounting for cash flows."""
    async with async_session() as session:
        port = await session.get(Portfolio, portfolio_id)
        if not port:
            return {"error": f"Portfolio {portfolio_id} not found"}

        target_currency = "USD"
        if port.account_id:
            acc = await session.get(Account, port.account_id)
            if acc:
                target_currency = acc.currency or "USD"

        result = await session.execute(
            select(PortfolioHolding)
            .where(PortfolioHolding.portfolio_id == portfolio_id)
        )
        holdings = result.scalars().all()
        if not holdings:
            return {"error": "No holdings in portfolio"}

        txn_result = await session.execute(
            select(Transaction.executed_at)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at.asc())
            .limit(1)
        )
        inception_date = txn_result.scalar()

        all_txns_result = await session.execute(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at.asc())
        )
        all_txns = all_txns_result.scalars().all()

        total_realized_pnl = 0.0
        total_dividends = 0.0

        records = []
        if all_txns:
            for t in all_txns:
                action = (t.action or "").lower()
                fx = t.exchange_rate or 1.0
                
                if "sell" in action and "split" not in action:
                    total_realized_pnl += (t.result_in_local or 0) * fx
                elif "dividend" in action:
                    total_dividends += (abs(t.total_in_local or 0) / fx) if fx > 0 else 0

                records.append({
                    "executed_at": t.executed_at,
                    "ticker": t.ticker,
                    "action": action,
                    "shares": t.shares,
                    "total_in_local": t.total_in_local or 0,
                    "price_per_share": t.price_per_share,
                })
        else:
            # Fallback for manual portfolios
            inception_date = min([h.added_at for h in holdings]) if holdings else datetime.now()
            for h in holdings:
                records.append({
                    "executed_at": h.added_at,
                    "ticker": h.ticker,
                    "action": "market buy",
                    "shares": h.shares,
                    "price_per_share": h.avg_cost_basis,
                    "total_in_local": h.shares * h.avg_cost_basis, # simplistic
                })

        total_realized_pnl = await convert_currency(total_realized_pnl, "USD", target_currency)
        total_dividends = await convert_currency(total_dividends, "USD", target_currency)

    df_txns = pd.DataFrame(records)
    if df_txns.empty:
        return {"error": "No transactions or holdings"}

    df_txns["executed_at"] = pd.to_datetime(df_txns["executed_at"]).dt.tz_localize(None).dt.normalize()
    inception_str = df_txns["executed_at"].min().strftime("%Y-%m-%d")
    today = datetime.now()

    all_tickers = df_txns["ticker"].unique().tolist()
    if not all_tickers:
        return {"error": "No active holdings"}

    benchmark_tickers = ["^GSPC", "^IXIC"]
    download_tickers = list(set(all_tickers + benchmark_tickers))

    def _download():
        data = yf.download(
            download_tickers,
            start=inception_str,
            end=(today + timedelta(days=1)).strftime("%Y-%m-%d"),
            auto_adjust=False,
            progress=False,
        )
        if data.empty:
            return pd.DataFrame()
        if len(download_tickers) == 1:
            return data
        return data["Close"] if "Close" in data.columns.get_level_values(0) else data

    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="yf_bench") as pool:
        close_df = await loop.run_in_executor(pool, _download)

    if close_df.empty:
        return {"error": "Could not fetch price data"}

    if isinstance(close_df.columns, pd.MultiIndex):
        close_df.columns = close_df.columns.get_level_values(-1)

    # Fallback for UK stocks that need .L suffix on Yahoo Finance
    missing_tickers = [t for t in all_tickers if t not in close_df.columns or close_df[t].isna().all()]
    if missing_tickers:
        def _download_l():
            l_tickers = [f"{t}.L" for t in missing_tickers]
            data = yf.download(
                l_tickers,
                start=inception_str,
                end=(today + timedelta(days=1)).strftime("%Y-%m-%d"),
                auto_adjust=False,
                progress=False,
            )
            if data.empty:
                return pd.DataFrame()
            return data["Close"] if "Close" in data.columns.get_level_values(0) else data

        with concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="yf_bench_l") as pool_l:
            close_l = await loop.run_in_executor(pool_l, _download_l)
            
        if not close_l.empty:
            if isinstance(close_l.columns, pd.MultiIndex):
                close_l.columns = close_l.columns.get_level_values(-1)
            close_l = close_l.rename(columns={f"{t}.L": t for t in missing_tickers})
            for t in missing_tickers:
                if t in close_l.columns and not close_l[t].isna().all():
                    close_df[t] = close_l[t]

    # Convert prices to target currency
    for ticker in all_tickers:
        if ticker in close_df.columns:
            currency = await get_cache(f"currency:{ticker}")
            if not currency:
                await get_live_price(ticker, fallback=0.0)
                currency = await get_cache(f"currency:{ticker}") or "USD"
            if currency == "GBP":
                close_df[ticker] = close_df[ticker] / 100.0
            
            if currency != target_currency:
                rate = await convert_currency(1.0, currency, target_currency)
                close_df[ticker] = close_df[ticker] * rate

    # Time-Weighted Return (TWR)
    rate_gbp = await convert_currency(1.0, "GBP", target_currency)
    
    # Filter transactions to only include tickers we have price data for, 
    # to avoid cash flows throwing off the return for missing assets.
    valid_tickers = [t for t in all_tickers if t in close_df.columns and not close_df[t].isna().all()]
    df_txns = df_txns[df_txns["ticker"].isin(valid_tickers)]
    
    def get_cf(row):
        action = row["action"]
        val = row["total_in_local"] * rate_gbp
        if "buy" in action:
            return val
        elif "sell" in action:
            return -val
        elif "dividend" in action:
            return -val
        return 0.0

    df_txns["cf"] = df_txns.apply(get_cf, axis=1)
    daily_cf = df_txns.groupby("executed_at")["cf"].sum()

    def get_share_change(row):
        action = row["action"]
        if "buy" in action or action == "stock split open":
            return row["shares"]
        elif ("sell" in action and "split" not in action) or action == "stock split close":
            return -row["shares"]
        return 0.0

    df_txns["share_change"] = df_txns.apply(get_share_change, axis=1)
    if "ticker" in df_txns.columns and not df_txns.empty:
        daily_shares = df_txns.groupby(["executed_at", "ticker"])["share_change"].sum().unstack(fill_value=0)
    else:
        daily_shares = pd.DataFrame()

    all_days = pd.date_range(inception_str, today.strftime("%Y-%m-%d"))
    if not daily_shares.empty:
        daily_shares = daily_shares.reindex(all_days).fillna(0).cumsum()
    else:
        daily_shares = pd.DataFrame(index=all_days)
        
    daily_cf = daily_cf.reindex(all_days).fillna(0)

    tickers_to_use = [t for t in daily_shares.columns if t in close_df.columns]
    
    if tickers_to_use:
        filled_prices = close_df[tickers_to_use].reindex(all_days).ffill().bfill()
        daily_value = (daily_shares[tickers_to_use] * filled_prices).sum(axis=1)
    else:
        daily_value = pd.Series(0.0, index=all_days)

    v_prev = daily_value.shift(1).fillna(0)
    with np.errstate(divide='ignore', invalid='ignore'):
        r_t = (daily_value - daily_cf) / v_prev - 1
    
    r_t = r_t.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    r_t.iloc[0] = 0.0
    portfolio_daily = r_t

    current_value = daily_value.iloc[-1] if not daily_value.empty else 0.0
    total_invested = daily_cf.sum()
    unrealized_pnl = current_value - total_invested

    total_return_pct = None
    if total_invested > 0:
        total_return_pct = round(
            ((unrealized_pnl + total_realized_pnl + total_dividends) / total_invested) * 100, 2
        )

    returns_df = close_df.pct_change()

    def cum_return(series, start_date=None):
        series = series.dropna()
        if start_date:
            series = series[series.index >= pd.Timestamp(start_date)]
        if series.empty:
            return None
        return round(float(((1 + series).cumprod().iloc[-1] - 1) * 100), 2)

    periods = {
        "1m": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
        "3m": (today - timedelta(days=90)).strftime("%Y-%m-%d"),
        "6m": (today - timedelta(days=180)).strftime("%Y-%m-%d"),
        "ytd": f"{today.year}-01-01",
        "1y": (today - timedelta(days=365)).strftime("%Y-%m-%d"),
        "since_inception": inception_str,
    }

    portfolio_returns = {}
    for period_key, start in periods.items():
        portfolio_returns[period_key] = cum_return(portfolio_daily, start)

    # Use TWR for since_inception to accurately compare against benchmarks.
    # The simple ROI is still available via total_return_pct.

    benchmarks = []
    for bm_ticker, bm_name in [("^GSPC", "S&P 500"), ("^IXIC", "NASDAQ")]:
        if bm_ticker not in returns_df.columns:
            continue
        bm_returns = {}
        for period_key, start in periods.items():
            bm_returns[period_key] = cum_return(returns_df[bm_ticker], start)
        benchmarks.append({
            "name": bm_name,
            "ticker": bm_ticker,
            "returns": bm_returns,
        })

    beta = None
    alpha = None
    sharpe = None
    risk_free_rate = 0.04

    if "^GSPC" in returns_df.columns:
        market_returns = returns_df["^GSPC"].fillna(0)
        aligned = pd.DataFrame({"port": portfolio_daily, "mkt": market_returns}).dropna()
        if len(aligned) > 30:
            cov_matrix = np.cov(aligned["port"], aligned["mkt"])
            market_var = cov_matrix[1, 1]
            if market_var > 0:
                beta = round(float(cov_matrix[0, 1] / market_var), 2)

            trading_days = len(aligned)
            port_annual = float(((1 + aligned["port"]).cumprod().iloc[-1]) ** (252 / trading_days) - 1)
            mkt_annual = float(((1 + aligned["mkt"]).cumprod().iloc[-1]) ** (252 / trading_days) - 1)

            if beta is not None:
                alpha = round((port_annual - (risk_free_rate + beta * (mkt_annual - risk_free_rate))) * 100, 2)

            port_std_annual = float(aligned["port"].std() * np.sqrt(252))
            if port_std_annual > 0:
                sharpe = round((port_annual - risk_free_rate) / port_std_annual, 2)

    return {
        "portfolio_return": portfolio_returns,
        "benchmarks": benchmarks,
        "beta": beta,
        "alpha": alpha,
        "sharpe_ratio": sharpe,
        "inception_date": inception_str,
        "total_invested": round(total_invested, 2),
        "current_value": round(current_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(total_realized_pnl, 2),
        "dividend_income": round(total_dividends, 2),
        "total_return_pct": total_return_pct,
        "currency": target_currency,
    }


@router.post("/portfolio/{portfolio_id}/holdings")
async def add_holding(portfolio_id: int, request: HoldingRequest):
    """Add a new holding to a portfolio."""
    async with async_session() as session:
        port = await session.get(Portfolio, portfolio_id)
        if not port:
            return {"error": f"Portfolio {portfolio_id} not found"}

        holding = PortfolioHolding(
            portfolio_id=portfolio_id,
            ticker=request.ticker.upper(),
            shares=request.shares,
            avg_cost_basis=request.avg_cost_basis,
        )
        session.add(holding)
        await session.commit()
        await session.refresh(holding)
        return {"id": holding.id, "ticker": holding.ticker, "shares": holding.shares, "avg_cost_basis": holding.avg_cost_basis}

@router.put("/portfolio/{portfolio_id}/holdings/{holding_id}")
async def update_holding(portfolio_id: int, holding_id: int, request: HoldingRequest):
    """Update an existing holding's shares or cost basis."""
    async with async_session() as session:
        holding = await session.get(PortfolioHolding, holding_id)
        if not holding or holding.portfolio_id != portfolio_id:
            return {"error": "Holding not found"}

        holding.ticker = request.ticker.upper()
        holding.shares = request.shares
        holding.avg_cost_basis = request.avg_cost_basis
        await session.commit()
        return {"id": holding.id, "ticker": holding.ticker, "shares": holding.shares, "avg_cost_basis": holding.avg_cost_basis}

@router.delete("/portfolio/{portfolio_id}/holdings/{holding_id}")
async def delete_holding(portfolio_id: int, holding_id: int):
    """Remove a holding from a portfolio."""
    async with async_session() as session:
        holding = await session.get(PortfolioHolding, holding_id)
        if not holding or holding.portfolio_id != portfolio_id:
            return {"error": "Holding not found"}

        await session.delete(holding)
        await session.commit()
        return {"deleted": True, "id": holding_id}

@router.post("/portfolio/{portfolio_id}/import/csv")
async def import_csv(portfolio_id: int, file: UploadFile = File(...)):
    """
    Import transactions from a Trading 212 CSV export.
    Stores every transaction row (buy/sell/dividend) with dedup by external_id.
    Recomputes holdings from the full transaction log.
    """
    from app.t212_import import parse_t212_transactions, compute_holdings

    if file.filename and not file.filename.lower().endswith('.csv'):
        return {"error": "Please upload a CSV file"}

    try:
        raw_bytes = await file.read()
        file_content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return {"error": "Could not decode file. Please ensure it is a UTF-8 CSV."}

    try:
        transactions = parse_t212_transactions(file_content)
    except ValueError as exc:
        return {"error": str(exc)}

    if not transactions:
        return {"error": "No transactions found in the CSV file."}

    async with async_session() as session:
        port = await session.get(Portfolio, portfolio_id)
        if not port:
            return {"error": f"Portfolio {portfolio_id} not found"}

        result = await session.execute(
            select(Transaction.external_id)
            .where(Transaction.portfolio_id == portfolio_id)
            .where(Transaction.external_id.isnot(None))
        )
        existing_ids = {row[0] for row in result.fetchall()}

        new_count = 0
        skipped_count = 0

        for txn in transactions:
            ext_id = txn.get("external_id")
            if ext_id and ext_id in existing_ids:
                skipped_count += 1
                continue

            record = Transaction(
                portfolio_id=portfolio_id,
                external_id=ext_id,
                action=txn["action"],
                ticker=txn["ticker"],
                name=txn.get("name", ""),
                isin=txn.get("isin", ""),
                shares=txn["shares"],
                price_per_share=txn["price_per_share"],
                currency=txn.get("currency", ""),
                exchange_rate=txn.get("exchange_rate"),
                total_in_local=txn.get("total_in_local"),
                result_in_local=txn.get("result_in_local"),
                executed_at=txn["executed_at"],
            )
            session.add(record)
            if ext_id:
                existing_ids.add(ext_id)
            new_count += 1

        await session.flush()

        all_txns_result = await session.execute(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at)
        )
        all_txns = [
            {
                "action": t.action,
                "ticker": t.ticker,
                "shares": t.shares,
                "price_per_share": t.price_per_share,
                "name": t.name,
            }
            for t in all_txns_result.scalars().all()
        ]

        computed = compute_holdings(all_txns)

        await session.execute(
            delete(PortfolioHolding)
            .where(PortfolioHolding.portfolio_id == portfolio_id)
        )

        for h in computed:
            if h["shares"] > 0:
                session.add(PortfolioHolding(
                    portfolio_id=portfolio_id,
                    ticker=h["ticker"],
                    shares=h["shares"],
                    avg_cost_basis=h["avg_cost_basis"],
                ))

        await session.commit()

    return {
        "new_transactions": new_count,
        "skipped": skipped_count,
        "total_in_csv": len(transactions),
        "holdings_count": len([h for h in computed if h["shares"] > 0]),
        "total_realized_pnl": round(sum(h["realized_pnl"] for h in computed), 2),
    }

@router.get("/portfolio/{portfolio_id}/transactions")
async def get_transactions(
    portfolio_id: int,
    ticker: str = Query(default=None, description="Filter by ticker"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Get paginated transaction history for a portfolio."""
    async with async_session() as session:
        query = (
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
        )
        count_query = (
            select(sqlfunc.count(Transaction.id))
            .where(Transaction.portfolio_id == portfolio_id)
        )

        if ticker:
            query = query.where(Transaction.ticker == ticker.upper())
            count_query = count_query.where(Transaction.ticker == ticker.upper())

        total = (await session.execute(count_query)).scalar() or 0

        query = query.order_by(Transaction.executed_at.desc()).limit(limit).offset(offset)
        result = await session.execute(query)
        txns = result.scalars().all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "transactions": [
                {
                    "id": t.id,
                    "external_id": t.external_id,
                    "action": t.action,
                    "ticker": t.ticker,
                    "name": t.name,
                    "shares": t.shares,
                    "price_per_share": round(t.price_per_share, 4),
                    "currency": t.currency,
                    "exchange_rate": round(t.exchange_rate, 6) if t.exchange_rate else None,
                    "total_in_local": round(t.total_in_local, 2) if t.total_in_local else None,
                    "result_in_local": round(t.result_in_local, 2) if t.result_in_local else None,
                    "executed_at": str(t.executed_at),
                }
                for t in txns
            ],
        }

@router.get("/portfolio/{portfolio_id}/realized")
async def get_realized_summary(portfolio_id: int):
    """
    Get aggregated realized P&L from sells and dividend income.
    Returns per-ticker breakdowns and totals.
    """
    async with async_session() as session:
        port = await session.get(Portfolio, portfolio_id)
        if not port:
            return {"error": f"Portfolio {portfolio_id} not found"}

        target_currency = "USD"
        if port.account_id:
            acc = await session.get(Account, port.account_id)
            if acc:
                target_currency = acc.currency or "USD"

        result = await session.execute(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.executed_at)
        )
        txns = result.scalars().all()

        sell_actions = {'market sell', 'limit sell'}
        sells_by_ticker = {}

        for t in txns:
            if t.action.lower() not in sell_actions:
                continue
            ticker = t.ticker
            if ticker not in sells_by_ticker:
                sells_by_ticker[ticker] = {
                    "ticker": ticker,
                    "name": t.name or ticker,
                    "total_proceeds": 0.0,
                    "total_realized_pnl": 0.0,
                    "total_shares_sold": 0.0,
                    "num_trades": 0,
                    "trades": [],
                }
            entry = sells_by_ticker[ticker]
            proceeds_local = t.total_in_local or 0
            result_local = t.result_in_local or 0

            proceeds_target = await convert_currency(proceeds_local, "GBP", target_currency)
            result_target = await convert_currency(result_local, "GBP", target_currency)

            ticker_currency = (await get_cache(f"currency:{t.ticker}")) or "USD"
            price_target = await convert_currency(t.price_per_share, ticker_currency, target_currency)

            entry["total_proceeds"] += proceeds_target
            entry["total_realized_pnl"] += result_target
            entry["total_shares_sold"] += t.shares
            entry["num_trades"] += 1
            entry["trades"].append({
                "date": str(t.executed_at)[:10] if t.executed_at else "",
                "shares": round(t.shares, 4),
                "price": round(price_target, 2),
                "proceeds": round(proceeds_target, 2),
                "pnl": round(result_target, 2),
            })

        realized_list = []
        for data in sorted(sells_by_ticker.values(), key=lambda x: -abs(x["total_realized_pnl"])):
            realized_list.append({
                "ticker": data["ticker"],
                "name": data["name"],
                "total_proceeds": round(data["total_proceeds"], 2),
                "total_realized_pnl": round(data["total_realized_pnl"], 2),
                "total_shares_sold": round(data["total_shares_sold"], 4),
                "num_trades": data["num_trades"],
                "trades": data["trades"],
            })

        dividends_by_ticker = {}

        for t in txns:
            if not t.action.lower().startswith("dividend"):
                continue
            ticker = t.ticker
            if ticker not in dividends_by_ticker:
                dividends_by_ticker[ticker] = {
                    "ticker": ticker,
                    "name": t.name or ticker,
                    "total_income": 0.0,
                    "total_withholding_tax": 0.0,
                    "num_payments": 0,
                    "payments": [],
                }
            entry = dividends_by_ticker[ticker]
            income_local = t.total_in_local or 0

            income_target = await convert_currency(income_local, "GBP", target_currency)

            ticker_currency = (await get_cache(f"currency:{t.ticker}")) or "USD"
            price_target = await convert_currency(t.price_per_share, ticker_currency, target_currency)

            entry["total_income"] += income_target
            entry["num_payments"] += 1
            entry["payments"].append({
                "date": str(t.executed_at)[:10] if t.executed_at else "",
                "shares": round(t.shares, 4),
                "per_share": round(price_target, 6),
                "income": round(income_target, 2),
            })

        dividend_list = []
        for data in sorted(dividends_by_ticker.values(), key=lambda x: -x["total_income"]):
            dividend_list.append({
                "ticker": data["ticker"],
                "name": data["name"],
                "total_income": round(data["total_income"], 2),
                "num_payments": data["num_payments"],
                "payments": data["payments"],
            })

        total_realized = round(sum(s["total_realized_pnl"] for s in realized_list), 2)
        total_dividends = round(sum(d["total_income"] for d in dividend_list), 2)

        return {
            "total_realized_pnl": total_realized,
            "total_dividend_income": total_dividends,
            "total_income": round(total_realized + total_dividends, 2),
            "realized": realized_list,
            "dividends": dividend_list,
            "currency": target_currency,
        }
