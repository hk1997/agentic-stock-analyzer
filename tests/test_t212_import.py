"""
Unit tests for the Trading 212 CSV import parser.
Covers parse_t212_transactions(), compute_holdings(), parse_t212_csv(),
and clean_t212_ticker() using realistic CSV format from actual T212 UK exports.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.t212_import import parse_t212_csv, parse_t212_transactions, compute_holdings, clean_t212_ticker


# ── Ticker Cleaning ──────────────────────────────────────────

class TestCleanT212Ticker:
    def test_us_equity_suffix(self):
        assert clean_t212_ticker("AAPL_US_EQ") == "AAPL"

    def test_plain_ticker(self):
        assert clean_t212_ticker("MSFT") == "MSFT"

    def test_eq_suffix(self):
        assert clean_t212_ticker("TSLA_EQ") == "TSLA"

    def test_empty(self):
        assert clean_t212_ticker("") == ""

    def test_whitespace(self):
        assert clean_t212_ticker("  NVDA  ") == "NVDA"

    def test_lowercase(self):
        assert clean_t212_ticker("goog") == "GOOG"


# ── Realistic CSV data ──────────────────────────────────────

HEADER = "Action,Time,ISIN,Ticker,Name,ID,No. of shares,Price / share,Currency (Price / share),Exchange rate,Result,Currency (Result),Total,Currency (Total),Withholding tax,Currency (Withholding tax),Currency conversion fee,Currency (Currency conversion fee)"


def make_csv(*rows: str) -> str:
    return HEADER + "\n" + "\n".join(rows)


# ── parse_t212_transactions ─────────────────────────────────

class TestParseT212Transactions:
    def test_parses_all_action_types(self):
        csv = make_csv(
            'Market buy,2025-04-28 14:33:00,US91324P1021,UNH,"UnitedHealth",EOF001,0.05,417.40,USD,1.33,,,,,"GBP",,,',
            'Market sell,2025-11-24 16:34:10,US91324P1021,UNH,"UnitedHealth",EOF002,3.75,320.00,USD,1.31,96.88,"GBP",914.30,"GBP",,,1.37,"GBP"',
            'Dividend (Dividend),2025-06-24 12:24:18,US91324P1021,UNH,"UnitedHealth",,0.61,1.88,USD,0.73,,,0.85,"GBP",0.20,USD,,',
        )
        result = parse_t212_transactions(csv)
        assert len(result) == 3
        assert result[0]["action"] == "Market buy"
        assert result[1]["action"] == "Market sell"
        assert result[2]["action"] == "Dividend (Dividend)"

    def test_preserves_external_id(self):
        csv = make_csv(
            'Market buy,2025-04-28 14:33:00,,UNH,"UnitedHealth",EOF31807912399,0.05,417.40,USD,1.33,,,,,,,,',
        )
        result = parse_t212_transactions(csv)
        assert result[0]["external_id"] == "EOF31807912399"

    def test_handles_missing_external_id(self):
        csv = make_csv(
            'Dividend (Dividend),2025-06-24 12:24:18,,UNH,"UnitedHealth",,0.61,1.88,USD,0.73,,,0.85,"GBP",,,,'
        )
        result = parse_t212_transactions(csv)
        assert result[0]["external_id"] is None

    def test_parses_timestamp(self):
        csv = make_csv(
            'Market buy,2025-04-28 14:33:00,,AAPL,"Apple",EOF001,10,150.00,USD,1.33,,,,,,,,',
        )
        result = parse_t212_transactions(csv)
        assert result[0]["executed_at"] is not None
        assert result[0]["executed_at"].year == 2025
        assert result[0]["executed_at"].month == 4

    def test_parses_result_for_sell(self):
        csv = make_csv(
            'Market sell,2025-10-01 14:58:37,,EOSE,"Eos Energy",EOF003,92.71,11.76,USD,1.35,408.05,"GBP",806.24,"GBP",,,1.21,"GBP"',
        )
        result = parse_t212_transactions(csv)
        assert result[0]["result_in_local"] == 408.05
        assert result[0]["total_in_local"] == 806.24

    def test_empty_csv(self):
        assert parse_t212_transactions("") == []

    def test_missing_columns_raises(self):
        with pytest.raises(ValueError, match="missing required columns"):
            parse_t212_transactions("Name,Quantity,Price\nApple,10,150")


# ── compute_holdings ─────────────────────────────────────────

class TestComputeHoldings:
    def test_buys_only(self):
        txns = [
            {"action": "Market buy", "ticker": "AAPL", "shares": 10, "price_per_share": 150, "name": "Apple"},
            {"action": "Market buy", "ticker": "AAPL", "shares": 5, "price_per_share": 200, "name": "Apple"},
        ]
        result = compute_holdings(txns)
        assert len(result) == 1
        assert result[0]["ticker"] == "AAPL"
        assert result[0]["shares"] == 15
        # Weighted avg: (10*150 + 5*200) / 15 = 166.67
        assert abs(result[0]["avg_cost_basis"] - 166.67) < 0.01
        assert result[0]["realized_pnl"] == 0

    def test_buy_then_sell(self):
        txns = [
            {"action": "Market buy", "ticker": "AAPL", "shares": 10, "price_per_share": 150, "name": "Apple"},
            {"action": "Market sell", "ticker": "AAPL", "shares": 5, "price_per_share": 200, "name": "Apple"},
        ]
        result = compute_holdings(txns)
        assert result[0]["shares"] == 5
        assert result[0]["avg_cost_basis"] == 150.0
        # Realized: 5 * (200 - 150) = 250
        assert abs(result[0]["realized_pnl"] - 250.0) < 0.01

    def test_full_sell(self):
        txns = [
            {"action": "Market buy", "ticker": "AAPL", "shares": 10, "price_per_share": 150, "name": "Apple"},
            {"action": "Market sell", "ticker": "AAPL", "shares": 10, "price_per_share": 180, "name": "Apple"},
        ]
        result = compute_holdings(txns)
        assert result[0]["shares"] == 0
        # Realized: 10 * (180 - 150) = 300
        assert abs(result[0]["realized_pnl"] - 300.0) < 0.01

    def test_sell_at_loss(self):
        txns = [
            {"action": "Market buy", "ticker": "AAPL", "shares": 10, "price_per_share": 200, "name": "Apple"},
            {"action": "Market sell", "ticker": "AAPL", "shares": 10, "price_per_share": 150, "name": "Apple"},
        ]
        result = compute_holdings(txns)
        assert result[0]["shares"] == 0
        # Realized: 10 * (150 - 200) = -500
        assert abs(result[0]["realized_pnl"] - (-500.0)) < 0.01

    def test_multiple_tickers(self):
        txns = [
            {"action": "Market buy", "ticker": "AAPL", "shares": 10, "price_per_share": 150, "name": "Apple"},
            {"action": "Market buy", "ticker": "MSFT", "shares": 5, "price_per_share": 350, "name": "Microsoft"},
        ]
        result = compute_holdings(txns)
        assert len(result) == 2
        tickers = {r["ticker"] for r in result}
        assert tickers == {"AAPL", "MSFT"}

    def test_limit_buy_and_sell(self):
        txns = [
            {"action": "Limit buy", "ticker": "AAPL", "shares": 10, "price_per_share": 150, "name": "Apple"},
            {"action": "Limit sell", "ticker": "AAPL", "shares": 5, "price_per_share": 200, "name": "Apple"},
        ]
        result = compute_holdings(txns)
        assert result[0]["shares"] == 5
        assert abs(result[0]["realized_pnl"] - 250.0) < 0.01

    def test_dividends_ignored(self):
        txns = [
            {"action": "Market buy", "ticker": "AAPL", "shares": 10, "price_per_share": 150, "name": "Apple"},
            {"action": "Dividend (Dividend)", "ticker": "AAPL", "shares": 10, "price_per_share": 0.20, "name": "Apple"},
        ]
        result = compute_holdings(txns)
        assert result[0]["shares"] == 10  # Dividend doesn't change shares

    def test_empty_transactions(self):
        assert compute_holdings([]) == []


# ── Legacy parse_t212_csv ────────────────────────────────────

class TestParseT212CsvLegacy:
    def test_single_buy(self):
        csv = make_csv(
            'Market buy,2025-04-28 14:33:00,,UNH,"UnitedHealth",EOF001,0.05,417.40,USD,1.33,,,,,,,,',
        )
        result = parse_t212_csv(csv)
        assert len(result) == 1
        assert result[0]["ticker"] == "UNH"

    def test_sell_excluded(self):
        csv = make_csv(
            'Market buy,2025-04-28 14:33:00,,UNH,"UnitedHealth",EOF001,10,300.00,USD,1.33,,,,,,,,',
            'Market sell,2025-11-24 16:34:10,,UNH,"UnitedHealth",EOF002,10,320.00,USD,1.31,,,,,,,,',
        )
        result = parse_t212_csv(csv)
        # Legacy only processes buys, so all shares are present
        assert result[0]["shares"] == 10

    def test_empty(self):
        assert parse_t212_csv("") == []
