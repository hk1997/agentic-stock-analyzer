"""
Unit tests for the CSV import parser.
Covers detect_and_parse_csv(), compute_holdings(), and clean_ticker() 
using realistic CSV formats (T212, Schwab/Meta, Morgan Stanley/Google).
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.csv_import import detect_and_parse_csv, compute_holdings, clean_ticker

# ── Ticker Cleaning ──────────────────────────────────────────

class TestCleanTicker:
    def test_us_equity_suffix(self):
        assert clean_ticker("AAPL_US_EQ") == "AAPL"

    def test_plain_ticker(self):
        assert clean_ticker("MSFT") == "MSFT"

    def test_eq_suffix(self):
        assert clean_ticker("TSLA_EQ") == "TSLA"

    def test_empty(self):
        assert clean_ticker("") == ""

    def test_whitespace(self):
        assert clean_ticker("  NVDA  ") == "NVDA"

    def test_lowercase(self):
        assert clean_ticker("goog") == "GOOG"

# ── Realistic CSV data ──────────────────────────────────────

HEADER_T212 = "Action,Time,ISIN,Ticker,Name,ID,No. of shares,Price / share,Currency (Price / share),Exchange rate,Result,Currency (Result),Total,Currency (Total),Withholding tax,Currency (Withholding tax),Currency conversion fee,Currency (Currency conversion fee)"

def make_t212_csv(*rows: str) -> str:
    return HEADER_T212 + "\n" + "\n".join(rows)

HEADER_SCHWAB = 'Date,Action,Symbol,Description,Quantity,Price,Fees & Comm,Amount'

def make_schwab_csv(*rows: str) -> str:
    # Schwab often has an extra top line, we add one to test skipping
    return "Transactions for account X\n" + HEADER_SCHWAB + "\n" + "\n".join(rows)

HEADER_MS = 'Release Date,Transaction Type,Participant Identifier,Name,Release Quantity,FairMarketValuePrice,Net Shares'

def make_ms_csv(*rows: str) -> str:
    return HEADER_MS + "\n" + "\n".join(rows)


# ── detect_and_parse_csv ─────────────────────────────────

class TestDetectAndParseCsv:
    def test_t212_parses_all_action_types(self):
        csv = make_t212_csv(
            'Market buy,2025-04-28 14:33:00,US91324P1021,UNH,"UnitedHealth",EOF001,0.05,417.40,USD,1.33,,,,,"GBP",,,',
            'Market sell,2025-11-24 16:34:10,US91324P1021,UNH,"UnitedHealth",EOF002,3.75,320.00,USD,1.31,96.88,"GBP",914.30,"GBP",,,1.37,"GBP"',
            'Dividend (Dividend),2025-06-24 12:24:18,US91324P1021,UNH,"UnitedHealth",,0.61,1.88,USD,0.73,,,0.85,"GBP",0.20,USD,,',
        )
        result = detect_and_parse_csv(csv)
        assert len(result) == 3
        assert result[0]["action"] == "market buy"
        assert result[1]["action"] == "market sell"
        assert result[2]["action"] == "dividend (dividend)"

    def test_t212_handles_gbp(self):
        csv = make_t212_csv(
            'Market buy,2025-04-28 14:33:00,,AAPL,"Apple",EOF001,10,15000.00,GBX,1.0,,,,,,,,',
        )
        result = detect_and_parse_csv(csv)
        assert result[0]["price_per_share"] == 150.0  # GBX / 100
        assert result[0]["currency"] == "GBP"

    def test_schwab_rsu_vest(self):
        csv = make_schwab_csv(
            '"05/15/2025","Restricted Stock Lapse","META","META PLATFORMS INC","10","300.50","0.00","3005.00"'
        )
        result = detect_and_parse_csv(csv)
        assert len(result) == 1
        assert result[0]["action"] == "market buy"  # RSU vest treated as market buy
        assert result[0]["ticker"] == "META"
        assert result[0]["shares"] == 10.0
        assert result[0]["price_per_share"] == 300.5
        assert result[0]["executed_at"].year == 2025

    def test_ms_rsu_vest(self):
        csv = make_ms_csv(
            '"2025-11-15","Release","12345","Alphabet Inc","15","150.25","9"'
        )
        result = detect_and_parse_csv(csv)
        assert len(result) == 1
        assert result[0]["action"] == "market buy"
        # We assume Alphabet guesses GOOGL or we just check Name parsing
        assert result[0]["shares"] == 15.0
        assert result[0]["price_per_share"] == 150.25

    def test_missing_columns_raises(self):
        with pytest.raises(ValueError):
            detect_and_parse_csv("Foo,Bar\n1,2")


# ── compute_holdings ─────────────────────────────────────────

class TestComputeHoldings:
    def test_buys_only(self):
        txns = [
            {"action": "market buy", "ticker": "AAPL", "shares": 10, "price_per_share": 150, "name": "Apple"},
            {"action": "market buy", "ticker": "AAPL", "shares": 5, "price_per_share": 200, "name": "Apple"},
        ]
        result = compute_holdings(txns)
        assert len(result) == 1
        assert result[0]["ticker"] == "AAPL"
        assert result[0]["shares"] == 15
        assert abs(result[0]["avg_cost_basis"] - 166.67) < 0.01
        assert result[0]["realized_pnl"] == 0

    def test_buy_then_sell(self):
        txns = [
            {"action": "market buy", "ticker": "AAPL", "shares": 10, "price_per_share": 150, "name": "Apple"},
            {"action": "market sell", "ticker": "AAPL", "shares": 5, "price_per_share": 200, "name": "Apple"},
        ]
        result = compute_holdings(txns)
        assert result[0]["shares"] == 5
        assert result[0]["avg_cost_basis"] == 150.0
        assert abs(result[0]["realized_pnl"] - 250.0) < 0.01

    def test_rsu_vesting(self):
        txns = [
            {"action": "market buy", "ticker": "META", "shares": 10, "price_per_share": 300, "name": "Meta"},
        ]
        result = compute_holdings(txns)
        assert result[0]["shares"] == 10
        assert result[0]["avg_cost_basis"] == 300.0
