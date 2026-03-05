import os
from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .llm import get_llm
from .agents.financial import create_financial_analyst
from functools import partial

# --- LLM Setup ---
llm = get_llm()

# --- Agents Setup ---
financial_analyst_node = create_financial_analyst(llm)

def build_graph():
    builder = StateGraph(AgentState)
    
    # Add Nodes
    # The frontend expects node names similar to the agents. 
    # We'll name this "FinancialAnalyst" so streaming UI works.
    builder.add_node("FinancialAnalyst", financial_analyst_node)
    
    # Simple flow: Start -> FinancialAnalyst -> End
    builder.add_edge(START, "FinancialAnalyst")
    builder.add_edge("FinancialAnalyst", END)
    
    # Compile the graph
    return builder.compile()
