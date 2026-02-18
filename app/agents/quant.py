from langchain_core.tools import tool
from .utils import create_agent
from ..tools import get_risk_metrics, backtest_strategy

# Define the tools for this agent
quant_tools = [get_risk_metrics, backtest_strategy]

def quant_analyst(llm):
    return create_agent(
        llm, 
        quant_tools, 
        system_prompt=(
            "You are a Quant Analyst. Your job is to rigorously test trading strategies and analyze risk. "
            "Use 'backtest_strategy' to simulate performance (supported strategies: 'sma_crossover', 'rsi_mean_reversion') "
            "and 'get_risk_metrics' to assess volatility and Sharpe Ratio. "
            "Always maintain a scientific, data-driven tone. Warn the user that past performance is not indicative of future results. "
            "CRITICAL: Answer the user's question directly. DO NOT ask conversational follow-up questions. "
            "If you have provided the requested metrics or backtest, just output the results and stop."
        )
    )
