try:
    from duckduckgo_search import DDGS
    print("SUCCESS: Imported duckduckgo_search.DDGS")
    with DDGS() as ddgs:
        results = list(ddgs.text("test", max_results=1))
        print(f"Results: {results}")
except ImportError as e:
    print(f"ERROR: {e}")
except Exception as e:
    print(f"ERROR RUNNING: {e}")
