import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState
from .agents.technical import technical_analyst
from .agents.sentiment import sentiment_analyst
from .agents.fundamental import fundamental_analyst
from .agents.supervisor import create_supervisor, supervisor_node
from functools import partial

# --- LLM Setup ---
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "gemini")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

print(f"Graph using Model Provider: {MODEL_PROVIDER} ({MODEL_NAME})")

if MODEL_PROVIDER == "ollama":
    llm = ChatOllama(model=MODEL_NAME)
else:
    llm = ChatGoogleGenerativeAI(model=MODEL_NAME)

# --- Agents Setup ---
# Create the specific agent nodes
technical_node = technical_analyst(llm)
sentiment_node = sentiment_analyst(llm)
fundamental_node = fundamental_analyst(llm)

# Create the supervisor chain
supervisor_chain = create_supervisor(llm)
# Create the supervisor node (partial processing to inject chain)
supervisor_node_func = partial(supervisor_node, supervisor_chain=supervisor_chain)

def build_graph():
    builder = StateGraph(AgentState)
    
    # Add Nodes
    builder.add_node("Supervisor", supervisor_node_func)
    builder.add_node("TechnicalAnalyst", technical_node)
    builder.add_node("SentimentAnalyst", sentiment_node)
    builder.add_node("FundamentalAnalyst", fundamental_node)
    
    # Entry Point
    builder.add_edge(START, "Supervisor")
    
    # Control Flow (Edges)
    # 1. Supervisor -> (Agent or End)
    builder.add_conditional_edges(
        "Supervisor",
        lambda x: x["next"],
        {
            "TechnicalAnalyst": "TechnicalAnalyst",
            "SentimentAnalyst": "SentimentAnalyst",
            "FundamentalAnalyst": "FundamentalAnalyst",
            "FINISH": END
        }
    )
    
    # 2. Agents -> Supervisor (Loop back)
    builder.add_edge("TechnicalAnalyst", "Supervisor")
    builder.add_edge("SentimentAnalyst", "Supervisor")
    builder.add_edge("FundamentalAnalyst", "Supervisor")
    
    # Memory
    checkpointer = MemorySaver()
    
    return builder.compile(checkpointer=checkpointer)
