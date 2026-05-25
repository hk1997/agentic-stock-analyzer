import csv
import json
import re
from datetime import datetime, timezone
import io
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.database import get_db_session
from app.models import User, Expense, Income, ManualAsset, NetWorthSnapshot, Portfolio, PortfolioHolding, LinkedAccount, ExpenseCategoryRule, RawExpense
from api.routes.auth import get_current_user

router = APIRouter(prefix="/api/finance", tags=["finance"])

class ExpenseCreate(BaseModel):
    date: datetime
    category: str
    amount: float
    description: str | None = None
    is_joint: bool = False

class ExpenseUpdate(BaseModel):
    category: str | None = None
    date: datetime | None = None
    amount: float | None = None
    description: str | None = None
    is_joint: bool | None = None
    ownership_type: str | None = None

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
    # Fetch linked user IDs
    links = await db.execute(select(LinkedAccount.linked_user_id).where(LinkedAccount.user_id == current_user.id))
    linked_ids = [r[0] for r in links.all()]
    
    # We want expenses owned by either current_user or any of their linked user accounts
    allowed_owner_ids = [current_user.id] + linked_ids
    query = select(Expense).where(Expense.owner_id.in_(allowed_owner_ids))
    
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

    # Fetch uploader/payer info from RawExpense
    expense_ids = [e.id for e in expenses]
    raw_expenses = {}
    if expense_ids:
        raw_res = await db.execute(
            select(RawExpense.expense_id, RawExpense.owner_id)
            .where(RawExpense.expense_id.in_(expense_ids))
        )
        for exp_id, owner_id in raw_res.all():
            raw_expenses[exp_id] = owner_id

    response = []
    for e in expenses:
        payer_id = raw_expenses.get(e.id, e.owner_id)
        response.append({
            "id": e.id,
            "owner_id": e.owner_id,
            "date": e.date,
            "category": e.category,
            "amount": e.amount,
            "description": e.description,
            "is_joint": e.is_joint,
            "created_at": e.created_at,
            "payer_id": payer_id
        })
    return response

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
    
    # Record current user as uploader/payer
    raw = RawExpense(
        owner_id=current_user.id,
        expense_id=expense.id,
        raw_data="{}"
    )
    db.add(raw)
    await db.commit()
    
    return {
        "id": expense.id,
        "owner_id": expense.owner_id,
        "date": expense.date,
        "category": expense.category,
        "amount": expense.amount,
        "description": expense.description,
        "is_joint": expense.is_joint,
        "created_at": expense.created_at,
        "payer_id": current_user.id
    }

@router.patch("/expenses/{expense_id}")
async def update_expense(
    expense_id: int,
    expense_in: ExpenseUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    # Fetch linked user IDs to permit linked account edits
    links = await db.execute(select(LinkedAccount.linked_user_id).where(LinkedAccount.user_id == current_user.id))
    linked_ids = [r[0] for r in links.all()]
    allowed_owner_ids = [current_user.id] + linked_ids

    result = await db.execute(
        select(Expense).where(
            and_(
                Expense.id == expense_id,
                Expense.owner_id.in_(allowed_owner_ids)
            )
        )
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
        
    if expense_in.category is not None:
        expense.category = expense_in.category
    if expense_in.date is not None:
        expense.date = expense_in.date
    if expense_in.amount is not None:
        expense.amount = expense_in.amount
    if expense_in.description is not None:
        expense.description = expense_in.description
        
    if expense_in.ownership_type is not None:
        if expense_in.ownership_type == "my-personal":
            expense.is_joint = 0
            expense.owner_id = current_user.id
        elif expense_in.ownership_type == "linked-personal":
            if not linked_ids:
                raise HTTPException(status_code=400, detail="No linked partner found to assign this expense to")
            expense.is_joint = 0
            expense.owner_id = linked_ids[0]
        elif expense_in.ownership_type == "joint":
            expense.is_joint = 1
    elif expense_in.is_joint is not None:
        expense.is_joint = 1 if expense_in.is_joint else 0
        
    await db.commit()
    await db.refresh(expense)

    # Check if a RawExpense exists, if not, insert a stub
    raw_res = await db.execute(select(RawExpense).where(RawExpense.expense_id == expense.id))
    raw = raw_res.scalar_one_or_none()
    if not raw:
        raw = RawExpense(
            owner_id=expense.owner_id,
            expense_id=expense.id,
            raw_data="{}"
        )
        db.add(raw)
        await db.commit()
        payer_id = expense.owner_id
    else:
        payer_id = raw.owner_id

    return {
        "id": expense.id,
        "owner_id": expense.owner_id,
        "date": expense.date,
        "category": expense.category,
        "amount": expense.amount,
        "description": expense.description,
        "is_joint": expense.is_joint,
        "created_at": expense.created_at,
        "payer_id": payer_id
    }

@router.delete("/expenses/{expense_id}")
async def delete_expense(
    expense_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    # Fetch linked user IDs to permit linked account deletes
    links = await db.execute(select(LinkedAccount.linked_user_id).where(LinkedAccount.user_id == current_user.id))
    linked_ids = [r[0] for r in links.all()]
    allowed_owner_ids = [current_user.id] + linked_ids

    result = await db.execute(
        select(Expense).where(
            and_(
                Expense.id == expense_id,
                Expense.owner_id.in_(allowed_owner_ids)
            )
        )
    )
    expense = result.scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
        
    await db.delete(expense)
    await db.commit()
    return {"status": "success"}

def parse_date(date_str: str) -> datetime:
    date_str = date_str.strip()
    if not date_str:
        raise ValueError("Empty date string")
    
    # Try ISO format (handles T and timezones)
    try:
        if date_str.endswith('Z'):
            date_str = date_str[:-1] + '+00:00'
        return datetime.fromisoformat(date_str)
    except ValueError:
        pass

    # Try common formats
    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y/%m/%d",
        "%b %d, %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {date_str}")

def parse_amount(amount_str: str) -> float:
    if not amount_str:
        return 0.0
    cleaned = amount_str.replace('$', '').replace('€', '').replace('£', '').replace(',', '').strip()
    return float(cleaned)

def detect_csv_columns(first_row: list[str]) -> dict[str, int] | None:
    # Try to identify Date, Description, Amount columns
    col_mapping = {}
    remaining_indices = list(range(len(first_row)))
    
    # 1. Identify Date column
    for i in remaining_indices:
        val = first_row[i].strip()
        try:
            parse_date(val)
            col_mapping['date'] = i
            remaining_indices.remove(i)
            break
        except ValueError:
            continue
            
    # 2. Identify Amount column
    for i in remaining_indices:
        val = first_row[i].strip()
        try:
            parse_amount(val)
            col_mapping['amount'] = i
            remaining_indices.remove(i)
            break
        except ValueError:
            continue
            
    # 3. Identify Description column
    if 'date' in col_mapping and 'amount' in col_mapping:
        if remaining_indices:
            col_mapping['description'] = remaining_indices[0]
            return col_mapping
            
    return None

@router.post("/expenses/upload")
async def upload_expenses_csv(
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    default_category: str | None = None,
    default_is_joint: bool | None = None,
    default_period: str | None = None,
    db: AsyncSession = Depends(get_db_session)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
    content = await file.read()
    try:
        decoded = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            decoded = content.decode('latin-1')
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Unable to decode file encoding. Please upload a UTF-8 or Latin-1 CSV file.")

    csv_data = list(csv.reader(io.StringIO(decoded)))
    if not csv_data:
        return {"status": "success", "added": 0, "uncategorized": 0}
        
    first_row = csv_data[0]
    col_mapping = detect_csv_columns(first_row)
    is_headerless = col_mapping is not None
    
    rows_to_process = []
    if is_headerless:
        for r in csv_data:
            if len(r) <= max(col_mapping.values()):
                continue
            rows_to_process.append({
                'date': r[col_mapping['date']],
                'amount': r[col_mapping['amount']],
                'description': r[col_mapping['description']],
                'category': 'Uncategorized',
                'is_joint': 'false',
                'raw_source': r
            })
    else:
        headers = [h.strip().lower() for h in first_row]
        for r in csv_data[1:]:
            if len(r) < len(headers):
                continue
            row_dict = dict(zip(headers, r))
            
            # Find the best header match for 'date', 'amount', 'description', 'category', 'is_joint'
            date_key = next((h for h in headers if 'date' in h), 'date')
            amount_key = next((h for h in headers if 'amount' in h or 'value' in h), 'amount')
            desc_key = next((h for h in headers if 'desc' in h or 'title' in h or 'memo' in h or 'payee' in h), 'description')
            cat_key = next((h for h in headers if 'cat' in h), 'category')
            joint_key = next((h for h in headers if 'joint' in h), 'is_joint')
            
            rows_to_process.append({
                'date': row_dict.get(date_key, ''),
                'amount': row_dict.get(amount_key, '0'),
                'description': row_dict.get(desc_key, ''),
                'category': row_dict.get(cat_key, 'Uncategorized'),
                'is_joint': row_dict.get(joint_key) or row_dict.get('isjoint') or 'false',
                'raw_source': r
            })
            
    # Check if there are any negative amounts to distinguish bank statements
    has_negative_amounts = False
    for r in rows_to_process:
        try:
            amt = parse_amount(r['amount'])
            if amt < 0:
                has_negative_amounts = True
                break
        except ValueError:
            continue

    rules_res = await db.execute(select(ExpenseCategoryRule).where(ExpenseCategoryRule.owner_id == current_user.id))
    rules = rules_res.scalars().all()
    
    # 1. Parse and validate all rows first, so we don't insert partial results
    # and can query DB counts before we start modifying database session state.
    parsed_rows = []
    failed_count = 0
    for r in rows_to_process:
        try:
            date_str = r['date'].strip()
            try:
                date_obj = parse_date(date_str)
                if date_obj.tzinfo is None:
                    date_obj = date_obj.replace(tzinfo=timezone.utc)
                if default_period:
                    try:
                        py, pm = map(int, default_period.split('-'))
                        import calendar
                        max_day = calendar.monthrange(py, pm)[1]
                        new_day = min(date_obj.day, max_day)
                        date_obj = date_obj.replace(year=py, month=pm, day=new_day)
                    except Exception:
                        pass
            except Exception:
                if default_period:
                    try:
                        py, pm = map(int, default_period.split('-'))
                        date_obj = datetime(py, pm, 1, tzinfo=timezone.utc)
                    except Exception:
                        raise
                else:
                    raise
            
            amount = parse_amount(r['amount'])
            
            if has_negative_amounts:
                if amount >= 0:
                    amount = -abs(amount)
                else:
                    amount = abs(amount)
            else:
                amount = abs(amount)

            description = r['description'].strip()
            if default_is_joint is not None:
                is_joint = 1 if default_is_joint else 0
            else:
                is_joint_val = r['is_joint']
                is_joint = 1 if str(is_joint_val).lower().strip() in ['true', '1', 'yes', 'y'] else 0

            parsed_rows.append({
                'date': date_obj,
                'amount': amount,
                'description': description,
                'is_joint': is_joint,
                'category': r.get('category', 'Uncategorized'),
                'raw_source': r['raw_source']
            })
        except Exception:
            failed_count += 1
            continue

    # 2. Query DB counts of all unique signatures in the CSV before inserting
    unique_signatures = set()
    for row in parsed_rows:
        unique_signatures.add((row['date'], row['amount'], row['description']))

    db_counts = {}
    for date_obj, amount, description in unique_signatures:
        count_res = await db.execute(
            select(func.count(Expense.id)).where(
                and_(
                    Expense.owner_id == current_user.id,
                    Expense.date == date_obj,
                    Expense.amount == amount,
                    Expense.description == description
                )
            )
        )
        db_counts[(date_obj, amount, description)] = count_res.scalar() or 0

    # 3. Process the rows and perform duplicate prevention
    session_imported_counts = {}
    added_count = 0
    duplicate_count = 0
    uncategorized_count = 0

    for row in parsed_rows:
        date_obj = row['date']
        amount = row['amount']
        description = row['description']
        sig = (date_obj, amount, description)

        db_cnt = db_counts.get(sig, 0)
        session_cnt = session_imported_counts.get(sig, 0)

        if session_cnt < db_cnt:
            # This occurrence of the transaction already exists in the database
            session_imported_counts[sig] = session_cnt + 1
            duplicate_count += 1
            continue

        session_imported_counts[sig] = session_cnt + 1

        category = "Uncategorized"
        if amount >= 0:
            for rule in rules:
                if description and re.search(rule.regex_pattern, description, re.IGNORECASE):
                    category = rule.category_name
                    break
                    
            if category == "Uncategorized":
                csv_cat = row['category']
                if csv_cat and csv_cat.strip():
                    category = csv_cat.strip()
                
            if category == "Uncategorized" and default_category:
                category = default_category.strip()

        if category == "Uncategorized":
            uncategorized_count += 1
        
        try:
            async with db.begin_nested():
                expense = Expense(
                    owner_id=current_user.id,
                    date=date_obj,
                    category=category,
                    amount=amount,
                    description=description,
                    is_joint=row['is_joint']
                )
                db.add(expense)
                await db.flush() # Needed to get expense.id
                
                raw = RawExpense(
                    owner_id=current_user.id,
                    expense_id=expense.id,
                    raw_data=json.dumps(row['raw_source'])
                )
                db.add(raw)
            added_count += 1
        except Exception:
            # Skip invalid rows and rollback subtransaction automatically via begin_nested()
            failed_count += 1
            continue
            
    if added_count > 0:
        await db.commit()
        
    return {
        "status": "success", 
        "added": added_count, 
        "duplicates": duplicate_count, 
        "failed": failed_count, 
        "uncategorized": uncategorized_count
    }

class CategoryRuleCreate(BaseModel):
    regex_pattern: str
    category_name: str

@router.post("/category-rules")
async def create_category_rule(
    rule_in: CategoryRuleCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    try:
        re.compile(rule_in.regex_pattern)
    except re.error:
        raise HTTPException(status_code=400, detail="Invalid regex pattern")

    # Prevent overly broad wildcard rules that match everything
    pattern_stripped = rule_in.regex_pattern.replace('.', '').replace('*', '').replace('?', '').strip()
    if not pattern_stripped:
        raise HTTPException(status_code=400, detail="Regex pattern is too broad and would match all descriptions")

    rule = ExpenseCategoryRule(
        owner_id=current_user.id,
        regex_pattern=rule_in.regex_pattern,
        category_name=rule_in.category_name
    )
    db.add(rule)
    
    # Apply retroactively
    expenses_res = await db.execute(
        select(Expense).where(
            and_(
                Expense.owner_id == current_user.id,
                Expense.category == "Uncategorized"
            )
        )
    )
    expenses = expenses_res.scalars().all()
    
    updated_count = 0
    for exp in expenses:
        if exp.description and re.search(rule.regex_pattern, exp.description, re.IGNORECASE):
            exp.category = rule.category_name
            updated_count += 1
            
    await db.commit()
    return {"status": "success", "rule_id": rule.id, "updated_expenses": updated_count}

@router.get("/expenses/uncategorized")
async def get_uncategorized_expenses(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(
        select(Expense).where(
            and_(
                Expense.owner_id == current_user.id,
                Expense.category == "Uncategorized"
            )
        ).order_by(Expense.date.desc())
    )
    expenses = result.scalars().all()

    # Fetch uploader/payer info from RawExpense
    expense_ids = [e.id for e in expenses]
    raw_expenses = {}
    if expense_ids:
        raw_res = await db.execute(
            select(RawExpense.expense_id, RawExpense.owner_id)
            .where(RawExpense.expense_id.in_(expense_ids))
        )
        for exp_id, owner_id in raw_res.all():
            raw_expenses[exp_id] = owner_id

    response = []
    for e in expenses:
        payer_id = raw_expenses.get(e.id, e.owner_id)
        response.append({
            "id": e.id,
            "owner_id": e.owner_id,
            "date": e.date,
            "category": e.category,
            "amount": e.amount,
            "description": e.description,
            "is_joint": e.is_joint,
            "created_at": e.created_at,
            "payer_id": payer_id
        })
    return response

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
