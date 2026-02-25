import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END

from .state import AgentState
from .agents.technical import technical_analyst
from .agents.sentiment import sentiment_analyst
from .agents.fundamental import fundamental_analyst
from .agents.valuation import valuation_analyst
from .agents.quant import quant_analyst
from .agents.supervisor import create_supervisor, supervisor_node
from .agents.classifier import create_classifier, classifier_node
from functools import partial

from .llm import get_llm

# --- LLM Setup ---
# Initialize LLM with Fallbacks
llm = get_llm()

# --- Agents Setup ---
# Create the specific agent nodes
technical_node = technical_analyst(llm)
sentiment_node = sentiment_analyst(llm)
fundamental_node = fundamental_analyst(llm)
valuation_node = valuation_analyst(llm)
quant_node = quant_analyst(llm)

# Create chains
classifier_chain = create_classifier(llm)
supervisor_chain = create_supervisor(llm)

# Create node functions
classifier_node_func = partial(classifier_node, classifier_chain=classifier_chain)
supervisor_node_func = partial(supervisor_node, supervisor_chain=supervisor_chain)

def max_steps_check(state: AgentState):
    """Fallback circuit breaker to prevent infinite loops."""
    if len(state["messages"]) > 10:
        return "FINISH"
    return state.get("next", "FINISH")

def build_graph():
    builder = StateGraph(AgentState)
    
    # Add Nodes
    builder.add_node("IntentClassifier", classifier_node_func)
    builder.add_node("Supervisor", supervisor_node_func)
    builder.add_node("TechnicalAnalyst", technical_node)
    builder.add_node("SentimentAnalyst", sentiment_node)
    builder.add_node("FundamentalAnalyst", fundamental_node)
    builder.add_node("ValuationAnalyst", valuation_node)
    builder.add_node("QuantAnalyst", quant_node)
    
    # Entry Point
    builder.add_edge(START, "IntentClassifier")
    
    builder.add_conditional_edges(
        "IntentClassifier",
        lambda x: x["next"],
        {
            "Supervisor": "Supervisor",
            "FINISH": END
        }
    )

    # Control Flow (Edges)
    # 1. Supervisor -> (Agent or End)
    builder.add_conditional_edges(
        "Supervisor",
        max_steps_check,
        {
            "TechnicalAnalyst": "TechnicalAnalyst",
            "SentimentAnalyst": "SentimentAnalyst",
            "FundamentalAnalyst": "FundamentalAnalyst",
            "ValuationAnalyst": "ValuationAnalyst",
            "QuantAnalyst": "QuantAnalyst",
            "FINISH": END
        }
    )
    
    # 2. Agents -> Supervisor (Loop back)
    # With token-streaming, it often makes sense to return directly to END after a specific specialist 
    # executes successfully, but letting the Supervisor check it first is safer.
    # We rely on max_steps_check to enforce termination.
    builder.add_edge("TechnicalAnalyst", "Supervisor")
    builder.add_edge("SentimentAnalyst", "Supervisor")
    builder.add_edge("FundamentalAnalyst", "Supervisor")
    builder.add_edge("ValuationAnalyst", "Supervisor")
    builder.add_edge("QuantAnalyst", "Supervisor")
    
    return builder
