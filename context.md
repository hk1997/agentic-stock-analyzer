# Agentic Stock Analyzer - Project Context

## Project Overview
**Goal:** A multi-agent AI system for dynamic stock analysis, combining real-time financial data (yfinance), news sentiment, and specialized agent personas to deliver comprehensive stock research insights via a premium, dark-mode glassmorphic React dashboard.

**Core Technologies:**
- **Backend:** FastAPI, LangGraph, LangChain (Google, Anthropic, Groq, Ollama), yfinance, SSE (Server-Sent Events)
- **Frontend:** React 19, Vite, TypeScript, Recharts, Lucide-React
- **Environments Strategy:** macOS file permission blocks (`EPERM` issues in `.venv` and `node_modules`) are bypassed by installing dependencies into `/tmp/stock-venv` and `/tmp/stock-ui-node` and creating symlinks back to the project root (`make setup`).

This document records what has been accomplished in this conversation thread and what is pending next.

---

## 1. What Has Been Achieved

### Phase 1: Architecture & Initial Routing (Complete)
- **LangGraph Strategy:** Designed a `Supervisor` agent that evaluates user input and passes the objective to one of 5 specialized agents (`TechnicalAnalyst`, `FundamentalAnalyst`, `SentimentAnalyst`, `ValuationAnalyst`, `QuantAnalyst`), or terminates the flow (`FINISH`).
- **LLM Factory:** Abstract logic in `app/llm.py` supporting `MODEL_PROVIDER` (gemini, ollama, anthropic, groq) and an `LLM_ORDER` fallback sequence from the `.env` file. A custom JSON logging callback is integrated for tracing execution.
- **State Definition:** Structured typing for `AgentState` including `messages`, `next` acting agent string, and visual tracking fields (`ticker`, `agent_steps`) built in `app/state.py`.

### Phase 2: Live Backend & React Frontend Scaffolding (Complete)
- **Environment Automation:** Created `scripts/setup.sh` and `Makefile` (`make setup`, `make dev-api`, `make dev-ui`, `make test`) for one-command environment builds.
- **Backend Upgrades:**
  - `api/main.py` upgraded to use `sse-starlette` for live streaming (`/api/chat/stream`). Emits `agent_start`, `agent_output`, `error`, and `finish` events as LangGraph yields them.
  - Implemented `/api/stock/{ticker}` using `yfinance` to power the frontend charts.
  - Test suite (`tests/test_api.py`) with 6 asynchronous tests covering endpoints cleanly utilizing Pytest (100% passing).
- **Frontend Re-scaffolding (`web-ui-v2/`):**
  - Fully scaffolded Vite/React/TS replacing Vanilla JS bypass approach.
  - Created a robust dark-mode glassmorphic design system (`index.css`) utilizing CSS variables with smooth glowing / backdrop filters.
  - Built pure React presentational components (`Sidebar`, `Header`, `StockChart` via Recharts, `StatCard`, `StatsRow`).
  - Built `ChatPanel` handling interactive real-time typing indicators for agents (`FundamentalAnalyst is analyzing...`).
  - Implemented custom hooks: `useChat.ts` (streams SSE data and manages threads) and `useStockData.ts` (asynchronously queries FastAPI for charting data).
  - Validated by 0 TypeScript errors and Vite production build succeeding (`dist/`). Included visual screenshots in the walkthrough.

---

## 2. What Is Pending (Next Steps)

### Phase 2: Real-time Integration (Iteration 3)
1. **End-to-End Chat Wiring:** Start both dev servers (`make dev-api`, `make dev-ui`). The `.env` file must be loaded holding API keys (`GOOGLE_API_KEY`, etc.).
2. **Execute a query:** Use `http://localhost:5173`. Ask `"Analyze AAPL"` and verify that `useChat` consumes the server stream and `useStockData` updates the `StockChart` and metrics concurrently.
3. Fix any CORS issues, SSE JSON decoding errors, or LangGraph instantiation errors that pop up during browser manipulation.

### Phase 3: Advanced Agent Capabilities
1. **Agent Implementation Details:** Right now, the routing works, but the internal logic of the specialized agents (`app/agents/*.py`) is either missing tools, throwing deprecation warnings (`create_react_agent` vs `from langchain.agents import create_agent` in `utils.py`), or has basic prompting.
2. **Real Tools:** We need to equip the `FundamentalAnalyst` and `TechnicalAnalyst` with genuine Python tools (e.g., pulling SEC EDGAR filings, calculating RSI/MACD with `pandas_ta`, or DDG Search for the `SentimentAnalyst`).

### Phase 4: Portfolio & Backtesting Engine
1. Integrate capabilities to save and manage user portfolios.
2. Develop a UI dashboard view connecting the `QuantAnalyst` to a backtesting engine framework (like `backtrader` or custom logic) to show historical performance grids.

---

## Technical Notes & Caveats
- **macOS Permissions:** Always run environments via `/tmp`. Do not run `npm install` inside `web-ui-v2` directly without the cache bypass, or `pip install` entirely locally. Use the `Makefile`.
- **API Keys**: Ensure they are consumed properly during FastAPI boot up and the LLM models correctly parse those environmental checks.
- **Testing:** Always run `pytest tests/` scoped appropriately locally since deep directory traversal attempts to stat the locked `.env` file breaking pytest execution. The `/tmp` test injection strategy exists as a workaround.
