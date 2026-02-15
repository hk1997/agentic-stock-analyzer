from app.tools import search_web

print("--- Testing Search Web ---")
query = "Why is AAPL stock moving today?"
print(f"Query: {query}")

try:
    result = search_web.invoke(query)
    print(f"\nResult:\n{result}")
except Exception as e:
    print(f"\nError:\n{e}")
