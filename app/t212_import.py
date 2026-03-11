"""
Trading 212 CSV Import Parser
Parses CSV exports from Trading 212 (UK Invest/ISA accounts).

Two modes:
1. parse_t212_transactions() — returns every row as a raw transaction dict
2. parse_t212_csv() — returns aggregated buy-only holdings (legacy compat)
3. compute_holdings() — derives net positions from a list of transactions
"""
import csv
import io
import re
from datetime import datetime
from typing import Optional


def clean_t212_ticker(raw_ticker: str) -> str:
    """
    Strip Trading 212 internal ticker suffixes to get a standard US ticker.
    Examples:
        AAPL_US_EQ  -> AAPL
        MSFT_US_EQ  -> MSFT
        AMZN        -> AMZN  (already clean in real exports)
    """
    if not raw_ticker:
        return raw_ticker
    # Remove known T212 suffixes like _US_EQ, _EQ, etc.
    cleaned = re.sub(r'_US_EQ$|_EQ$', '', raw_ticker.strip())
    return cleaned.upper()


def _get_field_map(fieldnames: list[str]) -> dict[str, str]:
    """Build a case-insensitive mapping of required columns to actual CSV column names."""
    required = {'Action', 'Ticker', 'No. of shares', 'Price / share'}
    found: set[str] = set()
    field_map: dict[str, str] = {}
    for f in fieldnames:
        for req in required:
            if f.strip().lower() == req.lower():
                found.add(req)
                field_map[req] = f.strip()

    missing = required - found
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

    # Optional columns — map if present
    optional = {'Time', 'ISIN', 'Name', 'ID', 'Currency (Price / share)',
                'Exchange rate', 'Total', 'Currency (Total)', 'Result', 'Currency (Result)'}
    for f in fieldnames:
        for opt in optional:
            if f.strip().lower() == opt.lower():
                field_map[opt] = f.strip()

    return field_map


def parse_t212_transactions(file_content: str) -> list[dict]:
    """
    Parse a Trading 212 CSV export and return ALL rows as transaction dicts.

    Returns a list of dicts, each representing one transaction:
    {
        "external_id": "EOF31807912399",
        "action": "Market buy",
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "isin": "US0378331005",
        "shares": 10.0,
        "price_per_share": 150.00,
        "currency": "USD",
        "exchange_rate": 1.3389,
        "total_in_local": 1500.00,
        "result_in_local": None,
        "executed_at": "2025-04-28T14:33:00",
    }
    """
    if not file_content or not file_content.strip():
        return []

    reader = csv.DictReader(io.StringIO(file_content))

    if not reader.fieldnames:
        raise ValueError("CSV file appears to be empty or has no headers")

    fieldnames = [f.strip() for f in reader.fieldnames]
    field_map = _get_field_map(fieldnames)

    transactions = []

    for row in reader:
        action = row.get(field_map.get('Action', 'Action'), '').strip()
        if not action:
            continue

        raw_ticker = row.get(field_map.get('Ticker', 'Ticker'), '').strip()
        ticker = clean_t212_ticker(raw_ticker)
        if not ticker:
            continue

        try:
            shares = float(row.get(field_map.get('No. of shares', 'No. of shares'), '0').strip() or '0')
            price = float(row.get(field_map.get('Price / share', 'Price / share'), '0').strip() or '0')
        except (ValueError, TypeError):
            continue  # Skip malformed rows

        # Parse optional fields
        name = row.get(field_map.get('Name', ''), '').strip() if 'Name' in field_map else ''
        isin = row.get(field_map.get('ISIN', ''), '').strip() if 'ISIN' in field_map else ''
        external_id = row.get(field_map.get('ID', ''), '').strip() if 'ID' in field_map else ''
        currency = row.get(field_map.get('Currency (Price / share)', ''), '').strip() if 'Currency (Price / share)' in field_map else ''

        # Exchange rate
        exchange_rate = None
        if 'Exchange rate' in field_map:
            try:
                er_val = row.get(field_map['Exchange rate'], '').strip()
                exchange_rate = float(er_val) if er_val else None
            except (ValueError, TypeError):
                pass

        # Total in local currency (GBP)
        total_in_local = None
        total_key = 'Total'
        if total_key in field_map:
            try:
                t_val = row.get(field_map[total_key], '').strip()
                total_in_local = float(t_val) if t_val else None
            except (ValueError, TypeError):
                pass

        # Result (for sells — realized P&L from T212)
        result_in_local = None
        if 'Result' in field_map:
            try:
                r_val = row.get(field_map['Result'], '').strip()
                result_in_local = float(r_val) if r_val else None
            except (ValueError, TypeError):
                pass

        # Parse timestamp
        time_str = row.get(field_map.get('Time', ''), '').strip() if 'Time' in field_map else ''
        executed_at = None
        if time_str:
            try:
                executed_at = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    executed_at = datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S')
                except ValueError:
                    pass

        transactions.append({
            "external_id": external_id or None,
            "action": action,
            "ticker": ticker,
            "name": name,
            "isin": isin,
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
    """
    Compute net holdings from a list of transaction dicts.

    Buy actions add shares, sell actions subtract shares.
    Cost basis is tracked as a weighted average of buys.
    Realized P&L is accumulated from sells.

    Returns a list of dicts:
    [{"ticker": "AAPL", "shares": 10.0, "avg_cost_basis": 150.00,
      "realized_pnl": 25.50, "name": "Apple Inc."}, ...]
    """
    buy_actions = {'market buy', 'limit buy'}
    sell_actions = {'market sell', 'limit sell'}

    # Track per ticker: total shares, total cost, realized P&L
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
            # Compute realized P&L using avg cost basis at time of sale
            current_avg_cost = (
                agg[ticker]["cost_total"] / agg[ticker]["shares"]
                if agg[ticker]["shares"] > 0 else 0
            )
            cost_of_sold = shares * current_avg_cost
            proceeds = shares * price
            agg[ticker]["realized_pnl"] += proceeds - cost_of_sold

            # Reduce shares and proportionally reduce cost basis
            agg[ticker]["shares"] -= shares
            agg[ticker]["cost_total"] -= cost_of_sold

            # Handle floating point edge cases
            if agg[ticker]["shares"] < 0.0001:
                agg[ticker]["shares"] = 0.0
                agg[ticker]["cost_total"] = 0.0

        elif action == "stock split close":
            # Split close removes old pre-split shares. Preserve cost basis.
            saved_cost = agg[ticker]["cost_total"]
            agg[ticker]["shares"] -= shares
            if agg[ticker]["shares"] < 0.0001:
                agg[ticker]["shares"] = 0.0
            # Proportionally reduce cost (will be restored by split open)
            if agg[ticker]["shares"] == 0:
                agg[ticker]["_split_cost"] = saved_cost
                agg[ticker]["cost_total"] = 0.0

        elif action == "stock split open":
            # Split open adds new post-split shares. Restore the cost basis.
            agg[ticker]["shares"] += shares
            # Restore cost basis from the split close
            if "_split_cost" in agg[ticker]:
                agg[ticker]["cost_total"] += agg[ticker].pop("_split_cost")
            else:
                agg[ticker]["cost_total"] += shares * price

    # Build result
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


def parse_t212_csv(file_content: str) -> list[dict]:
    """
    Legacy function: Parse a Trading 212 CSV and return aggregated buy-only holdings.
    Uses parse_t212_transactions() + compute_holdings() internally.
    """
    transactions = parse_t212_transactions(file_content)
    if not transactions:
        return []

    # Filter to buy-only for backward compat
    buy_actions = {'market buy', 'limit buy'}
    buy_txns = [t for t in transactions if any(t["action"].lower().startswith(ba) for ba in buy_actions)]

    if not buy_txns:
        return []

    holdings = compute_holdings(buy_txns)
    # Remove realized_pnl from legacy format
    return [
        {
            "ticker": h["ticker"],
            "shares": h["shares"],
            "avg_cost_basis": h["avg_cost_basis"],
            "name": h["name"],
        }
        for h in holdings
        if h["shares"] > 0
    ]
