import os
import uuid
from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
# Load environment variables
load_dotenv()

# Ensure API Key is set
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = input("Enter your Google API Key: ")

from app.graph import build_graph

def main():
    print("Stock Agent Ready. Type 'quit' to exit.")
    
    # Build the graph
    graph = build_graph()
    
    # Create a unique thread ID for this session
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    print(f"Session ID: {thread_id}")

    while True:
        user_query = input("\nUser: ")
        if user_query.lower() in ["exit", "quit", "q"]:
            break
        
        # Stream events with config
        events = graph.stream(
            {"messages": [("user", user_query)]},
            config=config,
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