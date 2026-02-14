import os
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
import yfinance as yf

# Load environment variables from .env file
load_dotenv()

# --- 1. Define the Tools ---
def fetch_stock_price(ticker: str):
    """Fetches the current stock price for a given ticker symbol (e.g., AAPL, TSLA)."""
    print(f"   [Tool] Fetching price for {ticker}...")
    stock = yf.Ticker(ticker)
    price = stock.history(period="1d")['Close'].iloc[-1]
    return f"The current price of {ticker} is ${price:.2f}"

# --- 2. Define the State ---
# This is the "memory" of our agent. It keeps track of the conversation.
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# --- 3. Initialize Gemini ---
# Ensure you have your API key set in your environment variables
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = input("Enter your Google API Key: ")

llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")

# --- 4. Define the Nodes ---
def agent_node(state: AgentState):
    """The Brain: Decides what to do next."""
    messages = state["messages"]
    # We simply ask the LLM. In a real agent, we'd bind tools here.
    # For Phase 1, we are keeping the logic explicit to show the flow.
    user_input = messages[-1].content
    
    # Simple logic: If it looks like a ticker request, we use the tool.
    # (Later, we will let Gemini decide this automatically via function calling)
    if "price" in user_input.lower():
        # Extract ticker roughly (upgrade this with an LLM tool call later)
        words = user_input.split()
        ticker = [w for w in words if w.isupper()][0] 
        return {"messages": [f"I will check the price for {ticker}."]}
    
    response = llm.invoke(messages)
    return {"messages": [response]}

def tool_node(state: AgentState):
    """The Hands: Executes the fetch."""
    last_message = state["messages"][-1].content
    # Extract ticker from the agent's internal thought process
    ticker = last_message.split()[-1].strip(".") 
    
    try:
        price_data = fetch_stock_price(ticker)
        return {"messages": [price_data]}
    except Exception as e:
        return {"messages": [f"Error fetching data: {e}"]}

# --- 5. Build the Graph ---
builder = StateGraph(AgentState)

# Add nodes
builder.add_node("agent", agent_node)
builder.add_node("tool", tool_node)

# Add edges (The flow)
builder.add_edge(START, "agent")

# Conditional logic: If the agent said "I will check...", go to tool. Otherwise END.
def should_continue(state: AgentState):
    last_message = state["messages"][-1].content
    if "I will check" in last_message:
        return "tool"
    return END

builder.add_conditional_edges("agent", should_continue, ["tool", END])
builder.add_edge("tool", END) # After fetching, stop (or go back to agent to summarize)

# Compile the graph
graph = builder.compile()

# --- 6. Run It ---
if __name__ == "__main__":
    while True:
        user_query = input("\nUser (type 'exit' to quit): ")
        if user_query.lower() in ["exit", "quit", "q"]:
            break
        
        events = graph.stream({"messages": [("user", user_query)]})

        for event in events:
            for value in event.values():
                # Check if the message is a base message (like AIMessage) or a string
                msg = value["messages"][-1]
                if hasattr(msg, "content"):
                    print("Agent:", msg.content)
                else:
                    print("Agent:", msg)