import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import ToolMessage
from .state import AgentState
from .tools import tools

# Valid providers: "gemini", "ollama"
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "gemini")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash")

print(f"Using Model Provider: {MODEL_PROVIDER} ({MODEL_NAME})")

if MODEL_PROVIDER == "ollama":
    llm = ChatOllama(model=MODEL_NAME)
else:
    llm = ChatGoogleGenerativeAI(model=MODEL_NAME)

# Bind tools to the LLM
llm_with_tools = llm.bind_tools(tools)

def agent_node(state: AgentState):
    """The Brain: Decides what to do next (Talk or Call Tool)."""
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def should_continue(state: AgentState):
    """Determines the next node based on the agent's response."""
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool"
    return END

def build_graph():
    """Builds and compiles the agent graph."""
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("agent", agent_node)
    builder.add_node("tool", ToolNode(tools))

    # Add edges
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, ["tool", END])
    builder.add_edge("tool", "agent")

    # Initialize memory
    checkpointer = MemorySaver()

    # Compile with checkpointer
    return builder.compile(checkpointer=checkpointer)
