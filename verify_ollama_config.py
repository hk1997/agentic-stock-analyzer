import os
from dotenv import load_dotenv

# Force environment to use Ollama for this test process
# (This overrides whatever is in .env or defaults)
os.environ["MODEL_PROVIDER"] = "ollama"
os.environ["MODEL_NAME"] = "llama3.1"

# We must import agent AFTER setting env vars because agent.py reads them at module level 
from app.agent import MODEL_PROVIDER, MODEL_NAME

print(f"--- Verification Script ---")
print(f"Configured Provider: {MODEL_PROVIDER}")
print(f"Configured Model: {MODEL_NAME}")

if MODEL_PROVIDER != "ollama":
    print("❌ ERROR: Agent did not pick up Ollama configuration.")
    exit(1)

print("✅ SUCCESS: Agent is configured to use Ollama.")
print("\nTo fully test, insure you have run: `ollama pull llama3.1`")
print("Then run: `python main.py`")
