from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage

from ..state import AgentState

class Intent(BaseModel):
    is_finance: bool = Field(description="True if the user query is about finance, stocks, companies, investing, or economics.")
    reasoning: str = Field(description="Brief explanation of why.")

def create_classifier(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert intent classifier. Determine if the user's query is related to finance, investing, stocks, companies, or the economy. If it is a general greeting like 'hello' or entirely off-topic, mark it as False."),
        ("user", "{query}")
    ])
    
    return prompt | llm.with_structured_output(Intent)

def classifier_node(state: AgentState, classifier_chain):
    # If there are multiple messages (i.e. we are deep in a conversation), skip classification
    if len(state["messages"]) > 1:
        return {"next": "Supervisor"}

    user_query = state["messages"][0].content
    result = classifier_chain.invoke({"query": user_query})
    
    if result.is_finance:
        return {"next": "Supervisor"}
    else:
        msg = AIMessage(content="I am a specialized financial stock analyzer agent. I can only assist with finance, stocks, valuation, and market analysis. Please ask me a financial question!")
        return {"messages": [msg], "next": "FINISH"}
