from dotenv import load_dotenv
load_dotenv()

from app.graph import build_graph
from langchain_core.messages import HumanMessage

app = build_graph()

def test_query(query: str):
    print(f"\n--- Testing Query: '{query}' ---")
    state = {"messages": [HumanMessage(content=query)]}
    
    try:
        for event in app.stream(state, config={"configurable": {"thread_id": "2"}}):
            for key, value in event.items():
                print(f"Node: {key}")
                if "next" in value:
                    print(f"  Supervisor Decision: {value['next']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_query("What sector is NVDA in and what do they do?")
    test_query("Is NVDA profitable? What is its P/E ratio?")
