from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

def create_agent(llm, tools, system_prompt: str):
    """Helper to create a standard ReAct agent."""
    # We use LangGraph's prebuilt create_react_agent for simplicity
    # This automatically handles tool calling loops
    return create_react_agent(llm, tools, prompt=system_prompt)
