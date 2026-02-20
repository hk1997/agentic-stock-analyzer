from langchain_core.tools import tool
from .utils import create_agent
from ..tools import search_web

# Define the tools for this agent
sentiment_tools = [search_web]

def sentiment_analyst(llm):
    return create_agent(
        llm, 
        sentiment_tools, 
        system_prompt=(
            "You are a Sentiment Analyst. Your job is to research news and market sentiment. "
            "Use the search tool to find recent news, earnings reports, and social sentiment to explain stock moves.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "- You are FORBIDDEN from searching for 'financial ratios', 'technical indicators', 'price history', or 'valuation models'.\n"
            "- IF the user asks for these, IGNORE that part of the request. Do not apologize.\n"
            "- FOCUS ONLY on news and sentiment."
        )
    )
