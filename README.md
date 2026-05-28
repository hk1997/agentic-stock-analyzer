# Agentic Stock Analyzer 📈🤖

A comprehensive, state-of-the-art wealth tracking and stock analysis application powered by a **Multi-Agent LangGraph Orchestrator**, a **FastAPI backend**, and a **React-Vite frontend (web-ui-v2)**.

The project features dynamic multi-currency asset tracking, account ledger transactions, net worth snapshots, and specialized AI agents that collaborate to answer user queries with real-time financial data.

---

## 📸 Dashboards

### Net Worth Page
Includes a dynamic resolution trend area chart, detailed asset/liability breakdowns, and real-time currency conversions showing your net worth in **USD**, **GBP (£)**, and **INR (₹)**.
![Net Worth Dashboard](docs/images/networth_dashboard.png)

### Portfolio Page
Tracks multi-currency holdings (e.g. US Equities, UK Equities, Indian Equities) with dynamic exchange rates, live market value pricing, asset allocation breakdowns, and benchmark performance comparison.
![Portfolio Dashboard](docs/images/portfolio_dashboard.png)

---

## 🛠️ Project Structure

```
/
├── api/                 # FastAPI Router & Endpoint Definitions
│   ├── routes/
│   │   ├── auth.py      # User authentication and registration
│   │   └── finance.py   # Account, Ledger, and Net Worth Snapshot routes
│   └── main.py          # Backend server entry & SSE chat stream
├── app/                 # LangGraph Multi-Agent Orchestrator
│   ├── agents/          # Specialized Analyst Agents (Tech, Fund, Quant, etc.)
│   ├── agent.py         # Main agent compile entrypoint
│   ├── cache.py         # Valkey/Redis cache & yfinance rate-limiting logic
│   └── database.py      # Async DB session and engine setup
├── web-ui-v2/           # React + TypeScript + Vite Web Application
│   ├── src/             # Components, hooks, and routing
│   └── package.json     # Node dependencies and scripts
├── tests/               # Python unit and integration test suite
├── docker-compose.yml   # Multi-service local deployment config
├── pyproject.toml       # Poetry python dependency management
└── README.md            # Project documentation
```

---

## 🚀 Core Features

### 1. Multi-Agent LangGraph Architecture
The application uses a **Supervisor-Worker Pattern** where a central orchestrator delegates complex analysis requests to specialized, isolated worker agents:
*   **Technical Analyst:** Calculates SMAs, RSI, MACD, and historical price indicators.
*   **Fundamental Analyst:** Evaluates balance sheets, P/E ratios, and company profiles.
*   **Sentiment/News Analyst:** Performs DuckDuckGo searches to find news explaining market movement.
*   **Valuation Analyst:** Generates DCF models based on systematic growth assumptions (CAPM, WACC).
*   **Quant Analyst:** Evaluates risk metrics (Sharpe ratio, volatility) and backtests strategies.

### 2. Multi-Currency Accounts & Portfolios
*   **Dynamic Exchange Rates:** Integrates with backend cache for live and fallback conversions across USD, GBP, and INR.
*   **Automatic Pence-to-Pounds Normalization:** UK stock symbols pricing (e.g. `GBp`/`GBX`) are automatically normalized to pounds (`GBP`).
*   **Direct USD Equivalents:** Bypasses double-conversion errors for accurate valuation representation.

### 3. Ledger Transactions & Cashflow
*   Log deposits, withdrawals, transfers, and expense rules.
*   Dynamically recalculates account balances on ledger adjustments.
*   Tracks joint splits and cost responsibilities.

---

## ⚡ Multi-Model Fallback 🛡️
Configure a fallback priority list in your `.env`. If a model fails or hits rate limits, the system automatically routes tasks to the next available provider (Gemini -> Groq -> Claude -> Local Ollama).

```bash
LLM_ORDER=gemini/gemini-2.5-flash,groq/llama-3.3-70b-versatile,anthropic/claude-3-haiku-20240307,ollama/llama3.1
```

---

## ⚙️ Setup & Installation

### Prerequisiutes
* Docker & Docker Compose
* Python 3.11+ (Poetry recommended)
* Node.js 18+

### Setup Environment
Create a `.env` file in the root directory:
```bash
GOOGLE_API_KEY=your_gemini_key
VALKEY_URL=redis://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/stock_analyzer
```

### Launch with Docker Compose
To run the entire system locally:
```bash
docker-compose up --build
```
*   **Frontend UI:** `http://localhost:5173`
*   **FastAPI Swagger Docs:** `http://localhost:8000/docs`
*   **Adminer DB Client:** `http://localhost:8080`

### Running Tests
Execute python unit and integration tests using Poetry:
```bash
poetry run pytest
```
