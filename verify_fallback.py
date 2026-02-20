import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Set a test configuration before importing app
# Testing Context Retention during Fallback
# Force failure on primary (ollama/invalid) -> Fallback to Secondary (groq)
os.environ["LLM_ORDER"] = "ollama/invalid-model,groq/llama-3.3-70b-versatile"

from app.llm import get_llm
from langchain_core.messages import HumanMessage, AIMessage

def test_fallback():
    print("\n--- Testing LLM Fallback with Context ---")
    try:
        llm = get_llm()
        print(f"LLM Object: {llm}")
        
        # Simulate a conversation history
        messages = [
            HumanMessage(content="My name is Hardik."),
            AIMessage(content="Hello Hardik! Nice to meet you."),
            HumanMessage(content="What is my name? Answer with just the name.")
        ]
        
        print("Invoking LLM with conversation history (Expect fallback from invalid-model -> groq)...")
        response = llm.invoke(messages)
        
        print(f"\nResponse: {response.content}")
        
        if "Hardik" in response.content:
            print("✅ SUCCESS: Context was retained during fallback!")
        else:
            print("❌ FAILURE: Context was lost.")
            
    except Exception as e:
        print(f"\nExample Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fallback()
