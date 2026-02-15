import inspect
from langgraph.prebuilt import create_react_agent

sig = inspect.signature(create_react_agent)
print(f"Signature: {sig}")
