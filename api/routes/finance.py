import csv
from datetime import datetime, timezone
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.database import get_db_session
from app.models import User, Expense, Income, ManualAsset, NetWorthSnapshot, Portfolio, PortfolioHolding, LinkedAccount
from api.routes.auth import get_current_user

router = APIRouter(prefix="/api/finance", tags=["finance"])

class ExpenseCreate(BaseModel):
    date: datetime
    category: str
    amount: float
    description: str | None = None
    is_joint: bool = False

class ManualAssetCreate(BaseModel):
    asset_type: str
    value: float
    description: str | None = None

# --- Expenses ---

@router.get("/expenses")
async def get_expenses(
    current_user: Annotated[User, Depends(get_current_user)],
    month: str | None = None, # format: YYYY-MM
    db: AsyncSession = Depends(get_db_session)
):
    query = select(Expense).where(
        (Expense.owner_id == current_user.id) | 
        (Expense.is_joint == 1) # Note: If joint, we'd theoretically need to check if the other owner is linked, but keeping it simple
    )
    
    if month:
        try:
            year, m = month.split('-')
            # Extract year/month from datetime in postgres
            query = query.where(
                and_(
                    func.extract('year', Expense.date) == int(year),
                    func.extract('month', Expense.date) == int(m)
                )
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid month format, expected YYYY-MM")
            
    result = await db.execute(query.order_by(Expense.date.desc()))
    expenses = result.scalars().all()
    
    # Filter joint expenses to only those from linked accounts
    if expenses:
        # Get linked account IDs
        links = await db.execute(select(LinkedAccount.linked_user_id).where(LinkedAccount.user_id == current_user.id))
        linked_ids = [r[0] for r in links.all()]
        
        filtered = []
        for e in expenses:
            if e.owner_id == current_user.id or (e.is_joint == 1 and e.owner_id in linked_ids):
                filtered.append(e)
        expenses = filtered
        
    return expenses

@router.post("/expenses")
async def create_expense(
    expense_in: ExpenseCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    expense = Expense(
        owner_id=current_user.id,
        date=expense_in.date,
        category=expense_in.category,
        amount=expense_in.amount,
        description=expense_in.description,
        is_joint=1 if expense_in.is_joint else 0
    )
    db.add(expense)
    await db.commit()
    await db.refresh(expense)
    return expense

@router.post("/expenses/upload")
async def upload_expenses_csv(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
    content = await file.read()
    decoded = content.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(decoded))
    
    added_count = 0
    for row in csv_reader:
        try:
            # Expected columns: Date, Category, Amount, Description, IsJoint
            date_str = row.get('Date', '').strip()
            date_obj = datetime.fromisoformat(date_str) if 'T' in date_str else datetime.strptime(date_str, "%Y-%m-%d")
            
            expense = Expense(
                owner_id=current_user.id,
                date=date_obj,
                category=row.get('Category', 'Uncategorized'),
                amount=float(row.get('Amount', 0)),
                description=row.get('Description', ''),
                is_joint=1 if str(row.get('IsJoint', '')).lower() in ['true', '1', 'yes'] else 0
            )
            db.add(expense)
            added_count += 1
        except Exception as e:
            # Skip invalid rows
            continue
            
    if added_count > 0:
        await db.commit()
        
    return {"status": "success", "added": added_count}

# --- Manual Assets ---

@router.get("/manual-assets")
async def get_manual_assets(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(select(ManualAsset).where(ManualAsset.owner_id == current_user.id))
    return result.scalars().all()

@router.post("/manual-assets")
async def add_manual_asset(
    asset_in: ManualAssetCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    asset = ManualAsset(
        owner_id=current_user.id,
        asset_type=asset_in.asset_type,
        value=asset_in.value,
        description=asset_in.description
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset

# --- Net Worth ---

@router.get("/net-worth-history")
async def get_net_worth_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    """
    Combines historical net worth snapshots with current live calculated net worth.
    """
    result = await db.execute(
        select(NetWorthSnapshot)
        .where(NetWorthSnapshot.owner_id == current_user.id)
        .order_by(NetWorthSnapshot.date)
    )
    history = result.scalars().all()
    
    # Calculate current live net worth
    # 1. Manual Assets
    asset_res = await db.execute(select(func.sum(ManualAsset.value)).where(ManualAsset.owner_id == current_user.id))
    manual_total = asset_res.scalar() or 0.0
    
    # 2. Portfolio Value (This requires a live fetch, but we'll approximate with last saved avg_cost_basis * shares 
    # if we don't want to block, or we rely on the client aggregating it. Let's do a basic DB sum for now).
    # Real implementation would call the portfolio endpoint logic to get live prices.
    port_res = await db.execute(select(Portfolio.id).where(Portfolio.owner_id == current_user.id))
    port_ids = [p[0] for p in port_res.all()]
    
    portfolio_total = 0.0
    if port_ids:
        holdings_res = await db.execute(
            select(PortfolioHolding.shares, PortfolioHolding.avg_cost_basis)
            .where(PortfolioHolding.portfolio_id.in_(port_ids))
        )
        # Note: This is cost basis, not live value. Live value needs yfinance.
        # For performance in a history endpoint, we use cost basis or a cached live value.
        for h in holdings_res.all():
            portfolio_total += h.shares * h.avg_cost_basis
            
    current_net_worth = manual_total + portfolio_total
    
    data = [{"date": s.date.strftime("%Y-%m-%d"), "net_worth": s.total_assets - s.total_liabilities} for s in history]
    
    # Append current
    data.append({
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), 
        "net_worth": current_net_worth,
        "is_live": True
    })
    
    return data

@router.get("/unified-portfolio")
async def get_unified_portfolio(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    """
    Returns a combined view of the current user's portfolio and any linked accounts' portfolios.
    For simplicity, we return the aggregated holdings.
    """
    # 1. Get user and linked user IDs
    user_ids = [current_user.id]
    links = await db.execute(select(LinkedAccount.linked_user_id).where(LinkedAccount.user_id == current_user.id))
    user_ids.extend([r[0] for r in links.all()])
    
    # 2. Get portfolios
    port_res = await db.execute(select(Portfolio.id).where(Portfolio.owner_id.in_(user_ids)))
    port_ids = [p[0] for p in port_res.all()]
    
    if not port_ids:
        return {"holdings": [], "total_value": 0, "total_cost": 0, "total_pnl": 0}
        
    # 3. Get holdings and aggregate by ticker
    holdings_res = await db.execute(
        select(PortfolioHolding)
        .where(PortfolioHolding.portfolio_id.in_(port_ids))
    )
    all_holdings = holdings_res.scalars().all()
    
    aggregated = {}
    for h in all_holdings:
        if h.ticker not in aggregated:
            aggregated[h.ticker] = {"shares": 0.0, "total_cost": 0.0}
        aggregated[h.ticker]["shares"] += h.shares
        aggregated[h.ticker]["total_cost"] += (h.shares * h.avg_cost_basis)
        
    # Real implementation would call yfinance here like in get_portfolio
    result = []
    total_value = 0.0
    total_cost = 0.0
    
    for ticker, data in aggregated.items():
        if data["shares"] > 0:
            avg_cost = data["total_cost"] / data["shares"]
            # Mock current price with cost basis for this simple aggregation
            current_price = avg_cost 
            current_value = data["shares"] * current_price
            total_value += current_value
            total_cost += data["total_cost"]
            result.append({
                "ticker": ticker,
                "shares": data["shares"],
                "avg_cost_basis": avg_cost,
                "current_price": current_price,
                "current_value": current_value,
                "unrealized_pnl": current_value - data["total_cost"]
            })
            
    return {
        "holdings": result,
        "total_value": total_value,
        "total_cost": total_cost,
        "total_pnl": total_value - total_cost
    }
