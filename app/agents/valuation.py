from langchain_core.tools import tool
from .utils import create_agent
from ..tools import get_free_cash_flow, calculate_intrinsic_value

# Define the tools for this agent
valuation_tools = [get_free_cash_flow, calculate_intrinsic_value]

def valuation_analyst(llm):
    return create_agent(
        llm, 
        valuation_tools, 
        system_prompt=(
            "You are a Valuation Analyst. Your job is to estimate the intrinsic value of a company "
            "using Discounted Cash Flow (DCF) analysis. "
            "Use 'calculate_intrinsic_value' to perform the valuation based on systematic assumptions "
            "(CAPM for discount rate, analyst estimates for growth). "
            "Explain the assumptions clearly to the user and compare the fair value to the current price.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "- Do NOT search for news.\n"
            "- Do NOT provide technical analysis."
        )
    )
