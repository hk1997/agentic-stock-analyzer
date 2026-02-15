# Agentic Stock Analyzer

A Python-based stock analysis tool leveraging LangGraph, Gemini, and yfinance to provide stock information. The project has evolved from manual logic to a fully autonomous agent using LLM function calling.

## Project Structure

```
/
├── main.py          # Core application logic (LangGraph, Gemini, Tools)
├── .env             # Environment variables (API Keys)
├── requirements.txt # Project dependencies
└── README.md        # Project documentation
```

## Features Implemented

### Phase 2: Autonomous Agent (Current)
*   **LLM Function Calling:** Replaced manual string parsing with native tool binding (`bind_tools`). The LLM now intelligently decides when to call `fetch_stock_price`.
*   **Gemini 2.5 Flash:** Upgraded to the latest efficient model for faster and more accurate responses.
*   **Robust Tooling:** 
    *   `fetch_stock_price` is now a proper LangChain `@tool`.
    *   Added error handling for invalid tickers (e.g., verifying `hist.empty`).
*   **Cyclic Graph Flow:** The graph now loops back (`Tool -> Agent`) so the agent can interpret the raw data and give a natural language response (e.g., "The price is $150").

### Phase 1: Foundation (Completed)
*   **LangGraph Integration:** Set up a stateful graph with `agent` and `tool` nodes.
*   **yfinance Integration:** Real-time stock data fetching.
*   **Interactive CLI:** Continuous user query loop.
*   **Environment Management:** Secure API key loading using `python-dotenv`.

## Architecture & Flow

### Autonomous Flow
The agent now uses a **cyclic** flow where the LLM drives the conversation and tool usage.

```mermaid
graph TD
    Start([User Input]) --> AgentNode[Agent Node]
    
    AgentNode -->|Decides to use Tool| ToolNode[Tool Node: fetch_stock_price]
    AgentNode -->|Final Answer| End([End Response])
    
    ToolNode -->|Raw Data| AgentNode
```

### Components
*   **Agent Node:** Receives user input or tool output. Uses `gemini-2.5-flash` to decide the next step (reply or call tool).
*   **Tool Node:** Executes the requested tool (e.g., `fetch_stock_price`) and returns a structured `ToolMessage`.
*   **Conditional Edge:** Inspects the LLM's response for `tool_calls`. If present, routes to the Tool Node; otherwise, ends the turn.

## Roadmap

- [x] **Phase 1: Foundation** (Manual Logic, Basic Graph)
- [x] **Phase 2: Autonomous Agent** (Function Calling, Cyclic Graph)
- [ ] **Phase 3: Advanced Analysis**
    - [ ] Add more tools (Technical Indicators, News Sentiment).
    - [ ] Implement multi-step reasoning (e.g., "Compare AAPL and MSFT").
    - [ ] Add persistence (PostgreSQL/SQLite) to remember conversations.

## Setup & Usage

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Configure Environment:**
    *   Create a `.env` file.
    *   Add your API key: `GOOGLE_API_KEY=your_key`.
3.  **Run:**
    ```bash
    python main.py
    ```
