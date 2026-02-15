import os
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
from langchain_core.messages import ToolMessage
import yfinance as yf
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()

# Commented lines are to list models 
# # Configure the raw client with your key
# genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# print("--- Available Models for your API Key ---")
# for m in genai.list_models():
#     if 'generateContent' in m.supported_generation_methods:
#         print(f"Name: {m.name}")

# --- 1. Define the Tools ---
@tool
def fetch_stock_price(ticker: str):
    """Fetches the current stock price for a given ticker symbol (e.g., AAPL, TSLA).
    
    Args:
        ticker: The stock ticker symbol.
    """
    print(f"\n   [System] Tool triggered: Fetching price for {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        # Verify data exists by checking history
        hist = stock.history(period="1d")
        if hist.empty:
            return f"Error: Could not find price data for {ticker}. Please check the symbol."
        price = hist['Close'].iloc[-1]
        return f"{price:.2f}"
    except Exception as e:
        return f"Error fetching price for {ticker}: {e}"

tools = [fetch_stock_price]

# --- 2. Define the State ---
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# --- 3. Initialize Gemini ---
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = input("Enter your Google API Key: ")

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

# BINDING: Attach tools to the model
llm_with_tools = llm.bind_tools(tools)

# --- 4. Define the Nodes ---
def agent_node(state: AgentState):
    """The Brain: Decides what to do next (Talk or Call Tool)."""
    messages = state["messages"]
    # The LLM now sees the tools and will decide whether to use them
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def tool_node(state: AgentState):
    """The Hands: Executes the tool requested by the LLM."""
    last_message = state["messages"][-1]
    
    # The LLM response includes 'tool_calls' if it wants to use a tool
    tool_calls = last_message.tool_calls
    
    results = []
    for t in tool_calls:
        # 1. Find the matching function
        if t['name'] == "fetch_stock_price":
            # 2. Run the function
            output = fetch_stock_price.invoke(t['args'])
            
            # 3. Create a ToolMessage (Required by LangGraph)
            results.append(ToolMessage(
                tool_call_id=t['id'],
                name=t['name'],
                content=str(output)
            ))
            
    return {"messages": results}

# --- 5. Build the Graph ---
builder = StateGraph(AgentState)

# Add nodes
builder.add_node("agent", agent_node)
builder.add_node("tool", tool_node)

# Add edges (The flow)
builder.add_edge(START, "agent")

# Conditional logic: Check if the LLM *wants* to call a tool
def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    # If the LLM response has tool calls attached, go to tool node
    if last_message.tool_calls:
        return "tool"
    # If not, the LLM is done talking
    return END

builder.add_conditional_edges("agent", should_continue, ["tool", END])

# IMPORTANT CHANGE: After the tool runs, go BACK to the agent.
# This allows Gemini to see the price and say "The price is $150" instead of just ending.
builder.add_edge("tool", "agent") 

# Compile the graph
graph = builder.compile()

# --- 6. Run It ---
if __name__ == "__main__":
    print("Stock Agent Ready. Type 'quit' to exit.")
    
    while True:
        user_query = input("\nUser: ")
        if user_query.lower() in ["exit", "quit", "q"]:
            break
        
        # We stream the events to see the thought process
        events = graph.stream(
            {"messages": [("user", user_query)]},
            stream_mode="values"
        )

        for event in events:
            # Get the latest message from the current state
            last_msg = event["messages"][-1]
            
            # If it's a Tool Execution (ToolMessage), we might want to hide it or print it differently
            if isinstance(last_msg, ToolMessage):
                # The tool output is usually raw data, we can skip printing it if we want cleaner output
                # or print it for debugging:2
                print(f"Tool Output: {last_msg.content}")
                pass 
                
            # If it's the Agent speaking (AIMessage)
            elif hasattr(last_msg, "content") and last_msg.content:
                print(f"Agent: {last_msg.content}")