from dotenv import load_dotenv
load_dotenv()

from app.graph import build_graph
from langchain_core.messages import HumanMessage

app = build_graph()

def test_query(query: str):
    print(f"\n--- Testing Query: '{query}' ---")
    state = {"messages": [HumanMessage(content=query)]}
    
    try:
        for event in app.stream(state, config={"configurable": {"thread_id": "4"}}):
            for key, value in event.items():
                print(f"Node: {key}")
                if "next" in value:
                    print(f"  Supervisor Decision: {value['next']}")
                
                # Check for messages in the state update
                if "messages" in value:
                    last_msg = value["messages"][-1]
                    print(f"  Message from Node: {last_msg.content[:500]}...") # Print more of message
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test routing to Quant Analyst
    test_query("What is the Sharpe Ratio and Volatility for TSLA?")
    test_query("Backtest a Golden Cross strategy on BTC-USD with $10,000.")
