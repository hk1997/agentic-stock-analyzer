from langchain_core.tools import tool
from .utils import create_agent
from ..tools import get_financial_metrics, get_company_info

# Define the tools for this agent
fundamental_tools = [get_financial_metrics, get_company_info]

def fundamental_analyst(llm):
    return create_agent(
        llm, 
        fundamental_tools, 
        system_prompt=(
            "You are a Fundamental Analyst. Your job is to analyze the financial health of a company. "
            "Use 'get_company_info' to understand what the company does and 'get_financial_metrics' "
            "to analyze its valuation and profitability. "
            "Look for red flags (e.g., high debt, low margins) and provide a professional assessment.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "- Do NOT search for 'latest news' or 'sentiment'.\n"
            "- Do NOT analyze charts or technical indicators."
        )
    )
