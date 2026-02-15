from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """The state of the agent, holding the conversation history."""
    messages: Annotated[list, add_messages]
