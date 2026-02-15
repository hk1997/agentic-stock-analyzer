from app.tools import fetch_stock_price, calculate_rsi, calculate_sma, calculate_macd

print("--- Testing Fetch Price ---")
print(fetch_stock_price.invoke({"ticker": "AAPL", "days": 1}))
print(fetch_stock_price.invoke({"ticker": "AAPL", "days": 3}))

print("\n--- Testing RSI ---")
print(calculate_rsi.invoke({"ticker": "AAPL"}))

print("\n--- Testing SMA ---")
print(calculate_sma.invoke({"ticker": "AAPL"}))

print("\n--- Testing MACD ---")
print(calculate_macd.invoke({"ticker": "AAPL"}))
