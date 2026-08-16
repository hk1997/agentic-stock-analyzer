import csv
import io
import re
from datetime import datetime

def clean_ticker(raw_ticker: str) -> str:
    if not raw_ticker:
        return raw_ticker
    cleaned = re.sub(r'_US_EQ$|_EQ$', '', raw_ticker.strip())
    return cleaned.upper()

def detect_and_parse_csv(file_content: str) -> list[dict]:
    if not file_content or not file_content.strip():
        return []

    # Some brokerages like Schwab have extra info at the top. 
    # We try to find the actual header row.
    lines = file_content.splitlines()
    start_idx = 0
    for i, line in enumerate(lines[:20]):
        lower_line = line.lower()
        if 'action' in lower_line or 'ticker' in lower_line or 'symbol' in lower_line or 'date' in lower_line or 'release date' in lower_line:
            start_idx = i
            break
            
    reader = csv.DictReader(lines[start_idx:])
    if not reader.fieldnames:
        raise ValueError("CSV file appears to be empty or has no recognizable headers")

    fieldnames = [f.strip() for f in reader.fieldnames]
    
    # Map normalized names to actual column names
    field_map = {}
    for f in fieldnames:
        fl = f.lower()
        if fl in ['action', 'type', 'transaction type', 'event']:
            field_map['Action'] = f
        elif fl in ['ticker', 'symbol', 'instrument', 'grant identifier']:
            field_map['Ticker'] = f
        elif fl in ['no. of shares', 'quantity', 'shares', 'release quantity', 'net shares']:
            field_map['Shares'] = f
        elif fl in ['price / share', 'price', 'fairmarketvalueprice', 'fmv']:
            field_map['Price'] = f
        elif fl in ['time', 'time (utc)', 'date', 'release date', 'transaction date']:
            field_map['Date'] = f
        elif fl in ['name', 'description']:
            field_map['Name'] = f
        elif fl in ['currency (price / share)', 'currency']:
            field_map['Currency'] = f
        elif fl in ['exchange rate']:
            field_map['Exchange rate'] = f
        elif fl in ['total', 'amount', 'net amount']:
            field_map['Total'] = f
        elif fl in ['result', 'realized p&l']:
            field_map['Result'] = f
        elif fl in ['id', 'transaction id', 'reference']:
            field_map['ID'] = f

    transactions = []

    for row in reader:
        action_val = row.get(field_map.get('Action', ''), '').strip().lower()
        
        # Meta/Schwab RSU vest is often "restricted stock lapse"
        # Google/Morgan Stanley might be "release" or "vest"
        is_rsu_vest = False
        if action_val in ['restricted stock lapse', 'lapse', 'release', 'vest', 'vesting']:
            action = 'market buy'
            is_rsu_vest = True
        else:
            action = action_val
            
        if not action:
            continue

        raw_ticker = row.get(field_map.get('Ticker', ''), '').strip()
        ticker = clean_ticker(raw_ticker)
        
        # For RSU platforms, they might not provide a ticker if it's single-company stock plan.
        # But we need one. We'll fallback to "UNKNOWN" and let the user edit it later,
        # or if the user uploads a Meta/Google CSV we could try to guess from the file name, 
        # but for now 'UNKNOWN' is safer if completely missing.
        if not ticker:
            if is_rsu_vest:
                # If they are uploading Meta/Google RSU vests without ticker, try to guess from description or just set to RSU
                desc = row.get(field_map.get('Name', ''), '').strip().lower()
                if 'meta' in desc or 'facebook' in desc:
                    ticker = 'META'
                elif 'google' in desc or 'alphabet' in desc:
                    ticker = 'GOOGL'
                else:
                    ticker = 'UNKNOWN'
            else:
                continue

        try:
            shares_str = row.get(field_map.get('Shares', ''), '0').strip().replace(',', '')
            shares = float(shares_str or '0')
            price_str = row.get(field_map.get('Price', ''), '0').strip().replace(',', '').replace('$', '')
            price = float(price_str or '0')
        except (ValueError, TypeError):
            continue  # Skip malformed rows

        if shares == 0:
            continue

        # Parse optional fields
        name = row.get(field_map.get('Name', ''), '').strip()
        external_id = row.get(field_map.get('ID', ''), '').strip()
        currency = row.get(field_map.get('Currency', ''), '').strip()

        if currency.upper() in ["GBP", "GBX"]:
            if currency in ["GBp", "GBX", "gbp", "gbx"]:
                price = price / 100.0
            currency = "GBP"

        # Exchange rate
        exchange_rate = None
        if 'Exchange rate' in field_map:
            try:
                er_val = row.get(field_map['Exchange rate'], '').strip()
                exchange_rate = float(er_val) if er_val else None
            except (ValueError, TypeError):
                pass

        # Total in local currency
        total_in_local = None
        if 'Total' in field_map:
            try:
                t_val = row.get(field_map['Total'], '').strip().replace(',', '').replace('$', '')
                total_in_local = float(t_val) if t_val else None
            except (ValueError, TypeError):
                pass

        # Result (for sells)
        result_in_local = None
        if 'Result' in field_map:
            try:
                r_val = row.get(field_map['Result'], '').strip().replace(',', '').replace('$', '')
                result_in_local = float(r_val) if r_val else None
            except (ValueError, TypeError):
                pass

        # Parse timestamp
        time_str = row.get(field_map.get('Date', ''), '').strip()
        executed_at = None
        if time_str:
            # Try multiple formats
            formats = [
                '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d',
                '%m/%d/%Y %H:%M:%S', '%m/%d/%Y', '%d/%m/%Y', '%d-%b-%Y'
            ]
            for fmt in formats:
                try:
                    executed_at = datetime.strptime(time_str, fmt)
                    break
                except ValueError:
                    continue
            if not executed_at:
                try:
                    executed_at = datetime.fromisoformat(time_str)
                except ValueError:
                    pass
                    
        # If still no date, default to now or skip
        if not executed_at:
            executed_at = datetime.now()

        transactions.append({
            "external_id": external_id or None,
            "action": action,
            "ticker": ticker,
            "name": name,
            "isin": "",
            "shares": shares,
            "price_per_share": price,
            "currency": currency,
            "exchange_rate": exchange_rate,
            "total_in_local": total_in_local,
            "result_in_local": result_in_local,
            "executed_at": executed_at,
        })

    return transactions

def compute_holdings(transactions: list[dict]) -> list[dict]:
    buy_actions = {'market buy', 'limit buy'}
    sell_actions = {'market sell', 'limit sell'}

    agg: dict[str, dict] = {}

    for txn in transactions:
        action = txn["action"].lower()
        ticker = txn["ticker"]
        shares = txn["shares"]
        price = txn["price_per_share"]

        if ticker not in agg:
            agg[ticker] = {
                "shares": 0.0,
                "cost_total": 0.0,
                "realized_pnl": 0.0,
                "name": txn.get("name", ""),
            }

        if any(action.startswith(ba) for ba in buy_actions):
            agg[ticker]["shares"] += shares
            agg[ticker]["cost_total"] += shares * price
            if txn.get("name"):
                agg[ticker]["name"] = txn["name"]

        elif any(action.startswith(sa) for sa in sell_actions):
            current_avg_cost = (
                agg[ticker]["cost_total"] / agg[ticker]["shares"]
                if agg[ticker]["shares"] > 0 else 0
            )
            cost_of_sold = shares * current_avg_cost
            proceeds = shares * price
            agg[ticker]["realized_pnl"] += proceeds - cost_of_sold

            agg[ticker]["shares"] -= shares
            agg[ticker]["cost_total"] -= cost_of_sold

            if agg[ticker]["shares"] < 0.0001:
                agg[ticker]["shares"] = 0.0
                agg[ticker]["cost_total"] = 0.0

        elif action == "stock split close":
            saved_cost = agg[ticker]["cost_total"]
            agg[ticker]["shares"] -= shares
            if agg[ticker]["shares"] < 0.0001:
                agg[ticker]["shares"] = 0.0
            if agg[ticker]["shares"] == 0:
                agg[ticker]["_split_cost"] = saved_cost
                agg[ticker]["cost_total"] = 0.0

        elif action == "stock split open":
            agg[ticker]["shares"] += shares
            if "_split_cost" in agg[ticker]:
                agg[ticker]["cost_total"] += agg[ticker].pop("_split_cost")
            else:
                agg[ticker]["cost_total"] += shares * price

    result = []
    for ticker, data in sorted(agg.items()):
        avg_cost = round(data["cost_total"] / data["shares"], 2) if data["shares"] > 0 else 0
        result.append({
            "ticker": ticker,
            "shares": round(data["shares"], 6),
            "avg_cost_basis": avg_cost,
            "realized_pnl": round(data["realized_pnl"], 2),
            "name": data["name"],
        })

    return result
