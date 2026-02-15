import os
from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
# Load environment variables
load_dotenv()

# Ensure API Key is set
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = input("Enter your Google API Key: ")

from app.agent import build_graph

def main():
    print("Stock Agent Ready. Type 'quit' to exit.")
    
    # Build the graph
    graph = build_graph()

    while True:
        user_query = input("\nUser: ")
        if user_query.lower() in ["exit", "quit", "q"]:
            break
        
        # Stream events
        events = graph.stream(
            {"messages": [("user", user_query)]},
            stream_mode="values"
        )

        for event in events:
            last_msg = event["messages"][-1]
            
            if isinstance(last_msg, ToolMessage):
                print(f"Tool Output: {last_msg.content}")
            elif hasattr(last_msg, "content") and last_msg.content:
                print(f"Agent: {last_msg.content}")

if __name__ == "__main__":
    main()