from typing import Annotated, Optional, TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """The state of the agent, holding the conversation history and metadata."""
    messages: Annotated[list, add_messages]
    next: str
    ticker: Optional[str]
    agent_steps: list[str]
