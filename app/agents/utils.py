from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

def create_agent(llm, tools, system_prompt: str):
    """Helper to create a standard ReAct agent."""
    # We use LangGraph's prebuilt create_react_agent for simplicity
    # This automatically handles tool calling loops
    # Prepend team instructions
    team_prompt = (
        "You are a specialized worker in a team of AI agents. "
        "Your role is defined below. "
        "You must focus ONLY on your specific task. "
        "Ignore any parts of the user request that are outside your scope. "
        "Do not apologize for not doing other tasks. "
        "Just perform your specific action and return the result.\n\n"
    )
    full_prompt = team_prompt + system_prompt
    
    return create_react_agent(llm, tools, prompt=full_prompt)
