import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq
from langchain_core.language_models.chat_models import BaseChatModel

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

class ModelNameLoggingHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        # serialized['name'] usually contains the model name/class
        model_name = (
            kwargs.get("metadata", {}).get("ls_model_name") or
            serialized.get("kwargs", {}).get("model_name") or 
            serialized.get("kwargs", {}).get("model") or 
            kwargs.get("invocation_params", {}).get("model") or
            kwargs.get("invocation_params", {}).get("model_name") or
            serialized.get("name")
        )
        print(f"\n[Model] Invoking: {model_name}")

    def on_llm_error(self, error: BaseException, **kwargs):
        print(f"[Model] Error: {error}")

    def on_llm_end(self, response: LLMResult, **kwargs):
        print(f"[Model] Finished")

def create_llm(provider: str, model_name: str) -> BaseChatModel:
    """Creates an LLM instance based on the provider."""
    print(f"Creating LLM: {provider}/{model_name}")
    provider = provider.lower()
    callbacks = [ModelNameLoggingHandler()]
    
    if provider == "google" or provider == "gemini":
        return ChatGoogleGenerativeAI(model=model_name, callbacks=callbacks)
    elif provider == "ollama":
        return ChatOllama(model=model_name, callbacks=callbacks)
    elif provider == "anthropic" or provider == "claude":
        return ChatAnthropic(model=model_name, callbacks=callbacks)
    elif provider == "groq":
        return ChatGroq(model=model_name, callbacks=callbacks)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

def get_llm() -> BaseChatModel:
    """
    Retrieves the LLM with fallback support based on LLM_ORDER environment variable.
    Format: provider/model,provider/model,...
    Example: gemini/gemini-2.5-flash,ollama/llama3.1
    """
    llm_order_str = os.getenv("LLM_ORDER")
    
    # Validation
    if not llm_order_str:
        # Fallback to legacy env vars if LLM_ORDER not set
        provider = os.getenv("MODEL_PROVIDER", "gemini")
        model = os.getenv("MODEL_NAME", "gemini-2.5-flash")
        return create_llm(provider, model)

    # Parse the order
    models = []
    entries = llm_order_str.split(",")
    
    for entry in entries:
        entry = entry.strip()
        if "/" not in entry:
             print(f"Warning: Invalid LLM entry format '{entry}'. Expected 'provider/model'. Skipping.")
             continue
        
        provider, model_name = entry.split("/", 1)
        try:
            llm = create_llm(provider, model_name)
            models.append(llm)
        except Exception as e:
            print(f"Error creating LLM for {entry}: {e}")

    if not models:
         raise ValueError("No valid LLMs could be created from LLM_ORDER.")

    # Setup Fallbacks
    primary_llm = models[0]
    if len(models) > 1:
        # The primary model will retry with the rest of the list in order
        backups = models[1:]
        print(f"Configuring Fallbacks: {len(backups)} backup model(s) available.")
        return primary_llm.with_fallbacks(backups)
    
    return primary_llm
