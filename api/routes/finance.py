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
from app.models import User, Expense, Income, ManualAsset, Account, NetWorthSnapshot, Portfolio, PortfolioHolding, LinkedAccount, ExpenseCategoryRule, RawExpense, FinancialGoal, GoalContribution, AccountTransaction
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

class AccountCreate(BaseModel):
    name: str
    classification: str
    account_class: str
    balance: float = 0.0
    currency: str = "USD"
    description: str | None = None

class AccountUpdate(BaseModel):
    name: str | None = None
    classification: str | None = None
    account_class: str | None = None
    balance: float | None = None
    currency: str | None = None
    description: str | None = None

class AccountTransactionCreate(BaseModel):
    amount: float
    transaction_type: str # "income", "expense", "transfer_out", "transfer_in"
    category: str | None = None
    description: str | None = None
    date: datetime

class AccountTransactionUpdate(BaseModel):
    amount: float | None = None
    transaction_type: str | None = None
    category: str | None = None
    description: str | None = None
    date: datetime | None = None

class TransferCreate(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: float
    description: str | None = None
    date: datetime

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

@router.delete("/manual-assets/{asset_id}")
async def delete_manual_asset(
    asset_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(
        select(ManualAsset).where(
            and_(
                ManualAsset.id == asset_id,
                ManualAsset.owner_id == current_user.id
            )
        )
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Manual asset not found")
        
    await db.delete(asset)
    await db.commit()
    return {"status": "success"}

# --- Accounts ---

import asyncio
import concurrent.futures
from app.cache import get_cache, set_cache, get_live_price

async def convert_currency(amount: float, from_curr: str, to_curr: str) -> float:
    from_curr = from_curr.upper().strip()
    to_curr = to_curr.upper().strip()
    if from_curr == to_curr or amount == 0.0:
        return amount
        
    cache_key = f"fx_rate:{from_curr}:{to_curr}"
    try:
        cached_rate = await get_cache(cache_key)
        if cached_rate is not None:
            return amount * float(cached_rate)
    except Exception:
        pass

    to_usd_rates = {
        "USD": 1.0,
        "GBP": 1.27,
        "EUR": 1.08,
        "INR": 0.012,
    }
    
    rate = None
    
    def fetch_rate(ticker_symbol):
        import yfinance as yf
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        val = info.get("regularMarketPrice") or info.get("previousClose") or info.get("currentPrice")
        if not val:
            hist = ticker.history(period="1d")
            if not hist.empty:
                val = float(hist["Close"].iloc[-1])
        return val

    # 1. Try to fetch from yfinance
    try:
        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            rate = await loop.run_in_executor(pool, fetch_rate, f"{from_curr}{to_curr}=X")
    except Exception:
        pass

    if not rate:
        # 2. Try inverse ticker
        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                inv_rate = await loop.run_in_executor(pool, fetch_rate, f"{to_curr}{from_curr}=X")
            if inv_rate:
                rate = 1.0 / inv_rate
        except Exception:
            pass

    if not rate:
        # 3. Static fallback rates
        if from_curr in to_usd_rates and to_curr in to_usd_rates:
            rate = to_usd_rates[from_curr] / to_usd_rates[to_curr]

    if not rate:
        rate = 1.0

    # Cache rate for 1 hour
    try:
        await set_cache(cache_key, str(rate), 3600)
    except Exception:
        pass

    return amount * rate

@router.get("/exchange-rates")
async def get_exchange_rates():
    usd_to_gbp = await convert_currency(1.0, "USD", "GBP")
    usd_to_inr = await convert_currency(1.0, "USD", "INR")
    usd_to_eur = await convert_currency(1.0, "USD", "EUR")
    return {
        "USD_TO_GBP": usd_to_gbp,
        "USD_TO_INR": usd_to_inr,
        "USD_TO_EUR": usd_to_eur
    }

@router.get("/accounts")
async def get_accounts(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(select(Account).where(Account.owner_id == current_user.id))
    accounts = result.scalars().all()
    response = []
    for a in accounts:
        balance = a.balance
        usd_value = None
        if a.account_class == "portfolio":
            port_res = await db.execute(select(Portfolio).where(Portfolio.account_id == a.id))
            portfolios = port_res.scalars().all()
            if portfolios:
                port_ids = [p.id for p in portfolios]
                holdings_res = await db.execute(select(PortfolioHolding).where(PortfolioHolding.portfolio_id.in_(port_ids)))
                holdings = holdings_res.scalars().all()
                portfolio_val_usd = 0.0
                for h in holdings:
                    price = await get_live_price(h.ticker, fallback=h.avg_cost_basis)
                    ticker_currency = (await get_cache(f"currency:{h.ticker}")) or "USD"
                    price_usd = await convert_currency(price, ticker_currency, "USD")
                    portfolio_val_usd += h.shares * price_usd
                
                balance = await convert_currency(portfolio_val_usd, "USD", a.currency)
                a.balance = balance
                usd_value = portfolio_val_usd

        if usd_value is None:
            usd_value = await convert_currency(balance, a.currency, "USD")
        response.append({
            "id": a.id,
            "owner_id": a.owner_id,
            "name": a.name,
            "classification": a.classification,
            "account_class": a.account_class,
            "balance": balance,
            "currency": a.currency,
            "description": a.description,
            "balance_usd": usd_value,
            "created_at": a.created_at,
            "updated_at": a.updated_at
        })
    return response

@router.post("/accounts")
async def add_account(
    account_in: AccountCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    account = Account(
        owner_id=current_user.id,
        name=account_in.name,
        classification=account_in.classification.lower().strip(),
        account_class=account_in.account_class.lower().strip(),
        balance=account_in.balance,
        currency=account_in.currency.upper().strip(),
        description=account_in.description
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    
    if account.account_class == "portfolio":
        portfolio = Portfolio(
            owner_id=current_user.id,
            account_id=account.id,
            name=f"{account.name} Portfolio"
        )
        db.add(portfolio)
        await db.commit()

    usd_value = await convert_currency(account.balance, account.currency, "USD")
    return {
        "id": account.id,
        "owner_id": account.owner_id,
        "name": account.name,
        "classification": account.classification,
        "account_class": account.account_class,
        "balance": account.balance,
        "currency": account.currency,
        "description": account.description,
        "balance_usd": usd_value,
        "created_at": account.created_at,
        "updated_at": account.updated_at
    }

@router.patch("/accounts/{account_id}")
async def update_account(
    account_id: int,
    account_in: AccountUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(
        select(Account).where(
            and_(
                Account.id == account_id,
                Account.owner_id == current_user.id
            )
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
        
    if account_in.name is not None:
        account.name = account_in.name
    if account_in.classification is not None:
        account.classification = account_in.classification.lower().strip()
    if account_in.account_class is not None:
        account.account_class = account_in.account_class.lower().strip()
    if account_in.balance is not None:
        account.balance = account_in.balance
    if account_in.currency is not None:
        account.currency = account_in.currency.upper().strip()
    if account_in.description is not None:
        account.description = account_in.description
        
    await db.commit()
    await db.refresh(account)
    
    usd_value = await convert_currency(account.balance, account.currency, "USD")
    return {
        "id": account.id,
        "owner_id": account.owner_id,
        "name": account.name,
        "classification": account.classification,
        "account_class": account.account_class,
        "balance": account.balance,
        "currency": account.currency,
        "description": account.description,
        "balance_usd": usd_value,
        "created_at": account.created_at,
        "updated_at": account.updated_at
    }

@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(
        select(Account).where(
            and_(
                Account.id == account_id,
                Account.owner_id == current_user.id
            )
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
        
    await db.delete(account)
    await db.commit()
    return {"status": "success"}

# --- Account Transactions & Transfers ---

@router.get("/accounts/{account_id}/transactions")
async def get_account_transactions(
    account_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    # Verify account ownership
    res = await db.execute(
        select(Account).where(
            and_(
                Account.id == account_id,
                Account.owner_id == current_user.id
            )
        )
    )
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    result = await db.execute(
        select(AccountTransaction)
        .where(AccountTransaction.account_id == account_id)
        .order_by(AccountTransaction.date.desc())
    )
    txs = result.scalars().all()
    return txs

@router.post("/accounts/{account_id}/transactions")
async def add_account_transaction(
    account_id: int,
    tx_in: AccountTransactionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    # Verify account ownership
    res = await db.execute(
        select(Account).where(
            and_(
                Account.id == account_id,
                Account.owner_id == current_user.id
            )
        )
    )
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    tx = AccountTransaction(
        account_id=account_id,
        amount=tx_in.amount,
        transaction_type=tx_in.transaction_type,
        category=tx_in.category,
        description=tx_in.description,
        date=tx_in.date
    )
    db.add(tx)
    account.balance += tx.amount
    await db.commit()
    await db.refresh(tx)
    return tx

@router.patch("/accounts/{account_id}/transactions/{transaction_id}")
async def update_account_transaction(
    account_id: int,
    transaction_id: int,
    tx_in: AccountTransactionUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    # Verify account ownership
    res = await db.execute(
        select(Account).where(
            and_(
                Account.id == account_id,
                Account.owner_id == current_user.id
            )
        )
    )
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Fetch transaction
    tx_res = await db.execute(
        select(AccountTransaction).where(
            and_(
                AccountTransaction.id == transaction_id,
                AccountTransaction.account_id == account_id
            )
        )
    )
    tx = tx_res.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Update balance and fields
    if tx_in.amount is not None:
        diff = tx_in.amount - tx.amount
        account.balance += diff
        tx.amount = tx_in.amount

        # Update linked transaction if it exists
        if tx.transfer_linked_transaction_id:
            linked_res = await db.execute(select(AccountTransaction).where(AccountTransaction.id == tx.transfer_linked_transaction_id))
            linked_tx = linked_res.scalar_one_or_none()
            if linked_tx:
                linked_acc_res = await db.execute(select(Account).where(Account.id == linked_tx.account_id))
                linked_acc = linked_acc_res.scalar_one_or_none()
                if linked_acc:
                    linked_diff = (-tx_in.amount) - linked_tx.amount
                    linked_acc.balance += linked_diff
                linked_tx.amount = -tx_in.amount

    if tx_in.transaction_type is not None:
        tx.transaction_type = tx_in.transaction_type
    if tx_in.category is not None:
        tx.category = tx_in.category
    if tx_in.description is not None:
        tx.description = tx_in.description
        if tx.transfer_linked_transaction_id:
            linked_res = await db.execute(select(AccountTransaction).where(AccountTransaction.id == tx.transfer_linked_transaction_id))
            linked_tx = linked_res.scalar_one_or_none()
            if linked_tx:
                linked_tx.description = tx_in.description
    if tx_in.date is not None:
        tx.date = tx_in.date
        if tx.transfer_linked_transaction_id:
            linked_res = await db.execute(select(AccountTransaction).where(AccountTransaction.id == tx.transfer_linked_transaction_id))
            linked_tx = linked_res.scalar_one_or_none()
            if linked_tx:
                linked_tx.date = tx_in.date

    await db.commit()
    await db.refresh(tx)
    return tx

@router.delete("/accounts/{account_id}/transactions/{transaction_id}")
async def delete_account_transaction(
    account_id: int,
    transaction_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    # Verify account ownership
    res = await db.execute(
        select(Account).where(
            and_(
                Account.id == account_id,
                Account.owner_id == current_user.id
            )
        )
    )
    account = res.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Fetch transaction
    tx_res = await db.execute(
        select(AccountTransaction).where(
            and_(
                AccountTransaction.id == transaction_id,
                AccountTransaction.account_id == account_id
            )
        )
    )
    tx = tx_res.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Subtract from balance and delete
    account.balance -= tx.amount

    # Delete linked transaction if it exists
    if tx.transfer_linked_transaction_id:
        linked_res = await db.execute(select(AccountTransaction).where(AccountTransaction.id == tx.transfer_linked_transaction_id))
        linked_tx = linked_res.scalar_one_or_none()
        if linked_tx:
            linked_acc_res = await db.execute(select(Account).where(Account.id == linked_tx.account_id))
            linked_acc = linked_acc_res.scalar_one_or_none()
            if linked_acc:
                linked_acc.balance -= linked_tx.amount
            await db.delete(linked_tx)

    await db.delete(tx)
    await db.commit()
    return {"status": "success"}

@router.post("/accounts/transfer")
async def transfer_funds(
    transfer_in: TransferCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    res_from = await db.execute(
        select(Account).where(
            and_(
                Account.id == transfer_in.from_account_id,
                Account.owner_id == current_user.id
            )
        )
    )
    from_account = res_from.scalar_one_or_none()
    if not from_account:
        raise HTTPException(status_code=404, detail="Source account not found")

    res_to = await db.execute(
        select(Account).where(
            and_(
                Account.id == transfer_in.to_account_id,
                Account.owner_id == current_user.id
            )
        )
    )
    to_account = res_to.scalar_one_or_none()
    if not to_account:
        raise HTTPException(status_code=404, detail="Destination account not found")

    tx_out = AccountTransaction(
        account_id=from_account.id,
        amount=-transfer_in.amount,
        transaction_type="transfer_out",
        category="Transfer",
        description=transfer_in.description or f"Transfer to {to_account.name}",
        date=transfer_in.date
    )
    db.add(tx_out)
    await db.flush()

    tx_in = AccountTransaction(
        account_id=to_account.id,
        amount=transfer_in.amount,
        transaction_type="transfer_in",
        category="Transfer",
        description=transfer_in.description or f"Transfer from {from_account.name}",
        date=transfer_in.date,
        transfer_linked_transaction_id=tx_out.id
    )
    db.add(tx_in)
    await db.flush()

    tx_out.transfer_linked_transaction_id = tx_in.id

    from_account.balance -= transfer_in.amount
    to_account.balance += transfer_in.amount

    await db.commit()
    return {"status": "success", "from_transaction_id": tx_out.id, "to_transaction_id": tx_in.id}

# --- Net Worth ---

async def capture_user_net_worth_snapshot(db: AsyncSession, user_id: int, target_date: datetime) -> NetWorthSnapshot:
    # 1. Manual Assets
    asset_res = await db.execute(select(func.sum(ManualAsset.value)).where(ManualAsset.owner_id == user_id))
    manual_total = asset_res.scalar() or 0.0

    # 2. Portfolio Value (only non-account portfolios)
    port_res = await db.execute(
        select(Portfolio.id).where(
            and_(
                Portfolio.owner_id == user_id,
                Portfolio.account_id == None
            )
        )
    )
    port_ids = [p[0] for p in port_res.all()]
    
    portfolio_total = 0.0
    if port_ids:
        holdings_res = await db.execute(
            select(PortfolioHolding.shares, PortfolioHolding.avg_cost_basis)
            .where(PortfolioHolding.portfolio_id.in_(port_ids))
        )
        for h in holdings_res.all():
            portfolio_total += h.shares * h.avg_cost_basis

    # 3. Account Balances (asset vs liability)
    accounts_res = await db.execute(select(Account).where(Account.owner_id == user_id))
    accounts = accounts_res.scalars().all()
    
    accounts_assets = 0.0
    accounts_liabilities = 0.0
    for a in accounts:
        balance = a.balance
        usd_bal = None
        if a.account_class == "portfolio":
            # calculate portfolio balance dynamically
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
        if a.classification == "liability":
            accounts_liabilities += usd_bal
        else:
            accounts_assets += usd_bal

    total_assets = manual_total + portfolio_total + accounts_assets
    total_liabilities = accounts_liabilities

    start_of_day = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    
    res = await db.execute(
        select(NetWorthSnapshot)
        .where(
            and_(
                NetWorthSnapshot.owner_id == user_id,
                func.date(NetWorthSnapshot.date) == start_of_day.date()
            )
        )
    )
    snapshot = res.scalar_one_or_none()
    if snapshot:
        snapshot.total_assets = total_assets
        snapshot.total_liabilities = total_liabilities
        snapshot.date = start_of_day
    else:
        snapshot = NetWorthSnapshot(
            owner_id=user_id,
            date=start_of_day,
            total_assets=total_assets,
            total_liabilities=total_liabilities
        )
        db.add(snapshot)
    
    await db.commit()
    await db.refresh(snapshot)
    return snapshot

@router.get("/net-worth-history")
async def get_net_worth_history(
    current_user: Annotated[User, Depends(get_current_user)],
    resolution: str = "daily",
    db: AsyncSession = Depends(get_db_session)
):
    """
    Combines historical net worth snapshots with current live calculated net worth.
    Supports resolution="daily" or "monthly".
    """
    today = datetime.now(timezone.utc)
    
    # Lazy log/update today's snapshot
    await capture_user_net_worth_snapshot(db, current_user.id, today)
    
    # Fetch all snapshots
    result = await db.execute(
        select(NetWorthSnapshot)
        .where(NetWorthSnapshot.owner_id == current_user.id)
        .order_by(NetWorthSnapshot.date)
    )
    snapshots = result.scalars().all()
    
    if resolution.lower().strip() == "monthly":
        monthly_snapshots = {}
        for s in snapshots:
            month_key = s.date.strftime("%Y-%m")
            # Since snapshots are ordered by date ascending, the last one seen per month key will be the latest for that month
            monthly_snapshots[month_key] = s
        snapshots_to_return = list(monthly_snapshots.values())
    else:
        snapshots_to_return = snapshots

    data = []
    today_str = today.strftime("%Y-%m-%d")
    for s in snapshots_to_return:
        s_date_str = s.date.strftime("%Y-%m-%d")
        data.append({
            "date": s_date_str,
            "net_worth": s.total_assets - s.total_liabilities,
            "total_assets": s.total_assets,
            "total_liabilities": s.total_liabilities,
            "is_live": s_date_str == today_str
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

# --- Financial Goals ---

class FinancialGoalCreate(BaseModel):
    title: str
    category: str
    target_amount: float
    target_date: datetime
    linked_asset_type: str | None = None
    linked_asset_id: int | None = None
    income_sources: str | None = None
    cash_flows: str | None = None

class FinancialGoalUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    target_amount: float | None = None
    target_date: datetime | None = None
    linked_asset_type: str | None = None
    linked_asset_id: int | None = None
    income_sources: str | None = None
    cash_flows: str | None = None

class GoalContributionCreate(BaseModel):
    amount: float
    date: datetime | None = None
    description: str | None = None

@router.get("/goals")
async def get_goals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    # 1. Fetch user and linked partner IDs
    links = await db.execute(select(LinkedAccount.linked_user_id).where(LinkedAccount.user_id == current_user.id))
    linked_ids = [r[0] for r in links.all()]
    all_user_ids = [current_user.id] + linked_ids
    
    # 2. Get user names for formatting
    users_res = await db.execute(select(User).where(User.id.in_(all_user_ids)))
    user_map = {u.id: (u.name or u.email.split('@')[0]) for u in users_res.scalars().all()}
    
    # 3. Fetch goals
    goals_res = await db.execute(
        select(FinancialGoal)
        .where(FinancialGoal.owner_id.in_(all_user_ids))
        .order_by(FinancialGoal.created_at.desc())
    )
    goals = goals_res.scalars().all()
    
    response = []
    for goal in goals:
        # Fetch contributions
        contribs_res = await db.execute(
            select(GoalContribution)
            .where(GoalContribution.goal_id == goal.id)
            .order_by(GoalContribution.date.desc())
        )
        contribs = contribs_res.scalars().all()
        
        # Calculate manual saved
        total_manual_saved = sum(c.amount for c in contribs)
        
        # Calculate partner breakdown
        partner_breakdown = {}
        for uid, name in user_map.items():
            label = "You" if uid == current_user.id else name
            partner_breakdown[label] = 0.0
            
        for c in contribs:
            c_label = "You" if c.contributor_id == current_user.id else user_map.get(c.contributor_id, "Partner")
            partner_breakdown[c_label] = partner_breakdown.get(c_label, 0.0) + c.amount
            
        # Calculate linked asset value
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
                
        total_saved = total_manual_saved + linked_asset_value
        progress_percent = min((total_saved / goal.target_amount) * 100, 100.0) if goal.target_amount > 0 else 0.0
        
        # Savings velocity: average contribution in last 3 months
        now = datetime.now(timezone.utc)
        goal_created = goal.created_at
        if goal_created.tzinfo is None:
            goal_created = goal_created.replace(tzinfo=timezone.utc)
            
        days_active = max((now - goal_created).days, 1)
        months_active = days_active / 30.0
        
        savings_velocity = total_manual_saved / months_active if months_active > 0.1 else total_manual_saved
        
        # Forecast months remaining
        remaining = goal.target_amount - total_saved
        if remaining <= 0:
            run_rate_months = 0.0
            status = "Complete"
        else:
            if savings_velocity > 0:
                run_rate_months = remaining / savings_velocity
            else:
                run_rate_months = None
                
            target_dt = goal.target_date
            if target_dt.tzinfo is None:
                target_dt = target_dt.replace(tzinfo=timezone.utc)
            months_to_target = (target_dt - now).days / 30.0
            
            if run_rate_months is not None and run_rate_months <= months_to_target:
                status = "On Track"
            else:
                status = "Behind"
                
        contribs_list = []
        for c in contribs:
            c_name = "You" if c.contributor_id == current_user.id else user_map.get(c.contributor_id, "Partner")
            contribs_list.append({
                "id": c.id,
                "goal_id": c.goal_id,
                "contributor_id": c.contributor_id,
                "contributor_name": c_name,
                "amount": c.amount,
                "date": c.date.isoformat(),
                "description": c.description
            })
            
        response.append({
            "id": goal.id,
            "owner_id": goal.owner_id,
            "owner_name": "You" if goal.owner_id == current_user.id else user_map.get(goal.owner_id, "Partner"),
            "title": goal.title,
            "category": goal.category,
            "target_amount": goal.target_amount,
            "target_date": goal.target_date.isoformat(),
            "linked_asset_type": goal.linked_asset_type,
            "linked_asset_id": goal.linked_asset_id,
            "income_sources": goal.income_sources,
            "cash_flows": goal.cash_flows,
            "created_at": goal.created_at.isoformat(),
            "contributions": contribs_list,
            "total_manual_saved": total_manual_saved,
            "linked_asset_value": linked_asset_value,
            "total_saved": total_saved,
            "progress_percent": progress_percent,
            "partner_breakdown": partner_breakdown,
            "savings_velocity": savings_velocity,
            "run_rate_months": run_rate_months,
            "status": status
        })
        
    return response

@router.post("/goals")
async def create_goal(
    goal_in: FinancialGoalCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    target_dt = goal_in.target_date
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)
        
    goal = FinancialGoal(
        owner_id=current_user.id,
        title=goal_in.title,
        category=goal_in.category,
        target_amount=goal_in.target_amount,
        target_date=target_dt,
        linked_asset_type=goal_in.linked_asset_type,
        linked_asset_id=goal_in.linked_asset_id,
        income_sources=goal_in.income_sources,
        cash_flows=goal_in.cash_flows
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return goal

@router.patch("/goals/{goal_id}")
async def update_goal(
    goal_id: int,
    goal_in: FinancialGoalUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    # Verify goal exists and belongs to user or linked partner
    links = await db.execute(select(LinkedAccount.linked_user_id).where(LinkedAccount.user_id == current_user.id))
    linked_ids = [r[0] for r in links.all()]
    allowed_owner_ids = [current_user.id] + linked_ids
    
    result = await db.execute(
        select(FinancialGoal).where(
            and_(
                FinancialGoal.id == goal_id,
                FinancialGoal.owner_id.in_(allowed_owner_ids)
            )
        )
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    if goal_in.title is not None:
        goal.title = goal_in.title
    if goal_in.category is not None:
        goal.category = goal_in.category
    if goal_in.target_amount is not None:
        goal.target_amount = goal_in.target_amount
    if goal_in.target_date is not None:
        target_dt = goal_in.target_date
        if target_dt.tzinfo is None:
            target_dt = target_dt.replace(tzinfo=timezone.utc)
        goal.target_date = target_dt
        
    if goal_in.linked_asset_type is not None:
        if goal_in.linked_asset_type == "none":
            goal.linked_asset_type = None
            goal.linked_asset_id = None
        else:
            goal.linked_asset_type = goal_in.linked_asset_type
            if goal_in.linked_asset_id is not None:
                goal.linked_asset_id = goal_in.linked_asset_id
    elif goal_in.linked_asset_id is not None:
        goal.linked_asset_id = goal_in.linked_asset_id
        
    if goal_in.income_sources is not None:
        goal.income_sources = goal_in.income_sources
    if goal_in.cash_flows is not None:
        goal.cash_flows = goal_in.cash_flows
        
    await db.commit()
    await db.refresh(goal)
    return goal

@router.post("/goals/{goal_id}/contributions")
async def add_goal_contribution(
    goal_id: int,
    contrib_in: GoalContributionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    links = await db.execute(select(LinkedAccount.linked_user_id).where(LinkedAccount.user_id == current_user.id))
    linked_ids = [r[0] for r in links.all()]
    allowed_owner_ids = [current_user.id] + linked_ids
    
    result = await db.execute(
        select(FinancialGoal).where(
            and_(
                FinancialGoal.id == goal_id,
                FinancialGoal.owner_id.in_(allowed_owner_ids)
            )
        )
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    contrib_date = contrib_in.date or datetime.now(timezone.utc)
    if contrib_date.tzinfo is None:
        contrib_date = contrib_date.replace(tzinfo=timezone.utc)
        
    contribution = GoalContribution(
        goal_id=goal.id,
        contributor_id=current_user.id,
        amount=contrib_in.amount,
        date=contrib_date,
        description=contrib_in.description
    )
    db.add(contribution)
    await db.commit()
    await db.refresh(contribution)
    return contribution

@router.delete("/goals/{goal_id}")
async def delete_goal(
    goal_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    links = await db.execute(select(LinkedAccount.linked_user_id).where(LinkedAccount.user_id == current_user.id))
    linked_ids = [r[0] for r in links.all()]
    allowed_owner_ids = [current_user.id] + linked_ids
    
    result = await db.execute(
        select(FinancialGoal).where(
            and_(
                FinancialGoal.id == goal_id,
                FinancialGoal.owner_id.in_(allowed_owner_ids)
            )
        )
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
        
    await db.delete(goal)
    await db.commit()
    return {"status": "success"}

@router.delete("/goals/{goal_id}/contributions/{contribution_id}")
async def delete_contribution(
    goal_id: int,
    contribution_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    links = await db.execute(select(LinkedAccount.linked_user_id).where(LinkedAccount.user_id == current_user.id))
    linked_ids = [r[0] for r in links.all()]
    allowed_owner_ids = [current_user.id] + linked_ids
    
    result = await db.execute(
        select(GoalContribution)
        .join(FinancialGoal, GoalContribution.goal_id == FinancialGoal.id)
        .where(
            and_(
                GoalContribution.id == contribution_id,
                GoalContribution.goal_id == goal_id,
                FinancialGoal.owner_id.in_(allowed_owner_ids)
            )
        )
    )
    contribution = result.scalar_one_or_none()
    if not contribution:
        raise HTTPException(status_code=404, detail="Contribution not found")
        
    await db.delete(contribution)
    await db.commit()
    return {"status": "success"}

@router.post("/send-monthly-summary")
async def send_monthly_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    month: str | None = None, # format: YYYY-MM
    db: AsyncSession = Depends(get_db_session)
):
    import re
    import os
    if month:
        if not re.match(r"^\d{4}-\d{2}$", month):
            raise HTTPException(status_code=400, detail="Invalid month format, expected YYYY-MM")
    else:
        import datetime
        month = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
        
    from app.email_service import run_monthly_summary_job
    success = await run_monthly_summary_job(db, current_user.id, month)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate or send the monthly summary email.")
        
    recipient = os.getenv("RECIPIENT_EMAIL") or current_user.email
    return {"status": "success", "message": "Monthly summary email sent successfully.", "recipient": recipient, "month": month}

