from langchain_core.tools import tool
from .utils import create_agent
from ..tools import fetch_stock_price, calculate_rsi, calculate_sma, calculate_macd

# Define the tools for this agent
technical_tools = [fetch_stock_price, calculate_rsi, calculate_sma, calculate_macd]

def technical_analyst(llm):
    return create_agent(
        llm, 
        technical_tools, 
        system_prompt=(
            "You are a Technical Analyst. Your job is to analyze stock price trends using technical indicators "
            "(RSI, Stock Price, MACD, etc.). Provide data-driven insights based on the charts.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "- Do NOT provide fundamental analysis (revenue, P/E).\n"
            "- Do NOT search for news."
        )
    )
