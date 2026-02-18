from typing import Literal
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.tools import tool

from ..state import AgentState

# The options the supervisor can choose from
# "FINISH" means reply to the user.
options = ["TechnicalAnalyst", "SentimentAnalyst", "FundamentalAnalyst", "ValuationAnalyst", "QuantAnalyst", "FINISH"]

# Using Pydantic to force the LLM to choose a valid next step
class route(BaseModel):
    next: Literal["TechnicalAnalyst", "SentimentAnalyst", "FundamentalAnalyst", "ValuationAnalyst", "QuantAnalyst", "FINISH"]

system_prompt = (
    "You are a Supervisor tasked with managing a conversation between the"
    " following workers: {members}. Given the following user request,"
    " respond with the worker to act next.\n\n"
    "Guide for choosing workers:\n"
    "- Use 'TechnicalAnalyst' for price charts, RSI, MACD, and trends.\n"
    "- Use 'FundamentalAnalyst' for business summary, sector, financial health, and ratios (P/E, Debt/Equity).\n"
    "- Use 'ValuationAnalyst' for estimating fair value, intrinsic value, or running DCF models.\n"
    "- Use 'QuantAnalyst' for backtesting trading strategies (SMA crossover, RSI reversion) or calculating risk metrics (Sharpe, Volatility).\n"
    "- Use 'SentimentAnalyst' for news, recent events, and public opinion.\n\n"
    "Each worker will perform a task and respond with results. "
    "CRITICAL: If the worker's response answers the user's question, you MUST respond with FINISH. "
    "Do not route back to the same worker unless there is a clear error."
)

def create_supervisor(llm):
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
            (
                "system",
                "Given the conversation above, who should act next?"
                " Or should we FINISH? Select one of: {options}",
            ),
        ]
    ).partial(options=str(options), members=", ".join(options))

    # Bind the "route" schema to the LLM (Function Calling)
    # We use 'with_structured_output' if available, or bind_functions generic approach
    # For robust cross-model support (Gemini/Ollama), we'll try a standard tool binding approach
    # or just use simple structured output if the model supports it well.
    # Since we support Ollama and Gemini, we should be careful.
    
    # Gemini supports with_structured_output natively in newer versions.
    # Ollama JSON mode is also an option.
    
    # Let's use the .with_structured_output method which is the modern LangChain standard
    supervisor_chain = (
        prompt
        | llm.with_structured_output(route)
    )
    
    return supervisor_chain

def supervisor_node(state: AgentState, supervisor_chain):
    result = supervisor_chain.invoke(state)
    return {"next": result.next}
