import os
import uuid
from dotenv import load_dotenv
from langchain_core.messages import ToolMessage, AIMessage
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
        
        # Stream events (default mode returns {node_name: state_update})
        events = graph.stream(
            {"messages": [("user", user_query)]},
            config=config,
            stream_mode="updates" 
        )

        for event in events:
            for node, values in event.items():
                print(f"\n--- Node Triggered: {node} ---")
                
                # Check for "next" routing decision
                if "next" in values:
                    print(f"Supervisor Decision: {values['next']}")
                
                # Check for messages
                if "messages" in values:
                    for msg in values["messages"]:
                        # 1. Check for Tool Calls (Agent asking to run a tool)
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                print(f"  [Action] Calling Tool: '{tool_call['name']}'")
                                print(f"  [Args]   {tool_call['args']}")
                        
                        # 2. Check for Tool Outputs
                        elif isinstance(msg, ToolMessage):
                            print(f"  [Result] Tool Output: {msg.content[:200]}..." if len(msg.content) > 200 else f"  [Result] Tool Output: {msg.content}")
                            
                        # 3. Check for Agent Text Response
                        elif hasattr(msg, "content") and msg.content:
                            print(f"  [Response] {msg.content}")

if __name__ == "__main__":
    main()