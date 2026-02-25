# Agentic Stock Analyzer - Detailed Roadmap

This document outlines a 5-phase roadmap for evolving the Agentic Stock Analyzer. It aims to balance technical robustness with business value, ensuring that the platform delivers accurate, performant, and reliable financial insights while maintaining a scalable and maintainable architecture.

---

## Phase 1: Foundation Solidification & Core Value Delivery
**Objective:** Focus on accurate data retrieval, environment stability, and immediate user value. Move away from hallucinatory multi-agent complexity until the baseline tools are rock-solid.

### Task 1.1: Environment & Dependency Standardization
*   **Business Lens:** Reduces onboarding friction for new developers or team members. Ensures the app can be reliably deployed to production environments (e.g., Vercel, Railway, AWS) without custom scripts or hacks, lowering maintenance costs.
*   **Technical Lens:** Replace the `/tmp` symlink hack for macOS permissions. Use standard package managers (`nvm`/`fnm` for Node, `pyenv`/`poetry` for Python). Containerize the backend and frontend using Docker for consistent cross-platform development and deployment.

### Task 1.2: Decoupling Data Fetching from LLM Routing
*   **Business Lens:** Drastically reduces "Time to First Value" (TTFV). Users want to see stock charts and basic stats immediately, not after a 15-second LLM inference delay. Lower API costs by avoiding LLM calls for deterministic data retrieval.
*   **Technical Lens:** Refactor the frontend so that entering a ticker triggers immediate REST API calls (e.g., `GET /api/stock/{ticker}`) for charts and stats. The LLM chat should be an *overlay* for deeper analysis, not the primary data retrieval mechanism.

### Task 1.3: Supercharging a Single "Financial Analyst" Agent
*   **Business Lens:** Prove the core product thesis: an AI that can perform deep, accurate financial analysis. A single, highly capable agent is more valuable than 5 agents with no real tools.
*   **Technical Lens:** Temporarily pause the 5-agent routing. Focus on equipping a single `FinancialAnalyst` agent with robust Python tools: `yfinance` for deep historical data, `pandas_ta` for technical indicators, and DuckDuckGo/News APIs for real-time sentiment. Ensure the agent can reliably chain these tools together without hallucinating.

---

## Phase 2: Advanced Analytical Capabilities & Data Integrity
**Objective:** Expand the depth of analysis the system can perform, ensuring data is accurate, explainable, and trustworthy.

### Task 2.1: Implementing SEC Edgar Document Retrieval
*   **Business Lens:** Transitions the product from a basic stock ticker tool to a professional-grade research assistant. Institutional investors rely on primary sources (10-Ks, 10-Qs).
*   **Technical Lens:** Integrate the `sec-api` or a similar SEC EDGAR parser. Build tools that allow the agent to fetch, parse, and summarize specific sections (e.g., "Management's Discussion and Analysis") of recent filings.

### Task 2.2: Deterministic Valuation Modeling
*   **Business Lens:** Provides actionable, quantitative insights (e.g., "AAPL is undervalued by 15% based on a DCF model"). This is highly sought after by retail and institutional investors alike.
*   **Technical Lens:** Build deterministic Python tools for Discounted Cash Flow (DCF), Dividend Discount Model (DDM), and sum-of-the-parts valuations. The agent should *gather the inputs* (growth rates, discount rates) but the *math* must be handled by deterministic code, not LLM reasoning, to ensure absolute accuracy.

### Task 2.3: Data Persistence & Caching Strategy
*   **Business Lens:** Significantly reduces API costs (e.g., yfinance rate limits, external news API costs) and dramatically improves user experience by returning instantaneous historical data and company profiles from a database rather than fetching them live every time.
*   **Technical Lens:** 
    *   **Database (PostgreSQL/MongoDB):** Store static or slowly-changing data: Company Profiles (industry, sector, executive summaries), historical end-of-day price data, and past calculated metrics (like historical P/E ratios).
    *   **Cache (Redis):** Store highly volatile data: Intraday price quotes, real-time news sentiment scores, and recent LLM analysis outputs (to prevent redundant LLM inference for the same query within a short time window).

### Task 2.4: Data Tracing and Explainability
*   **Business Lens:** Builds user trust. If the AI says a stock is overvalued, the user needs to know *why* and see the raw data sources.
*   **Technical Lens:** Upgrade the frontend chat interface to show "Tool Execution" drawers. When the agent calculates an RSI or reads a news article, provide a collapsible UI element showing the exact API response or source link used.

---

## Phase 3: The Multi-Agent Renaissance (Done Right)
**Objective:** Reintroduce the multi-agent architecture only when specialized personas are necessary for handling extreme complexity or conflicting data points.

### Task 3.1: Re-architecting the Supervisor Pattern
*   **Business Lens:** Optimizes API spend and latency. Only route to specialists when a query requires deep, multi-disciplinary analysis (e.g., "Compare TSLA's technical setup with its current fundamental valuation and recent news sentiment").
*   **Technical Lens:** Re-implement the `Supervisor` node, but with a cheaper, faster LLM (or even a fast structured intent classifier) for routing. Ensure the supervisor can intelligently synthesize conflicting opinions from the specialists (e.g., Technical Analyst says "Buy", Fundamental Analyst says "Sell").

### Task 3.2: Dedicated "Quant" and "Sentiment" Specialists
*   **Business Lens:** Offers diverse market perspectives. The Quant agent appeals to technical traders, while the Sentiment agent appeals to momentum/news traders.
*   **Technical Lens:**
    *   **Quant Analyst:** Integrate backtesting frameworks (`backtrader` or custom metrics). Allow the agent to run historical simulations (e.g., "What if I bought every time RSI dipped below 30?").
    *   **Sentiment Analyst:** Deepen news integration. Aggregate social media sentiment (if APIs are available/affordable) and perform entity-specific sentiment scoring.

### Task 3.3: Collaborative Debate Mechanism
*   **Business Lens:** Generates massive value by simulating an investment committee. Users get a nuanced, comprehensive view of a stock rather than a one-sided opinion.
*   **Technical Lens:** Implement a LangGraph flow where agents can "debate" or pass context to each other before the Supervisor renders a final verdict to the user.

---

## Phase 4: Personalization, Portfolios, & Persistence
**Objective:** Transition the app from a stateless research tool to a personalized investment companion.

### Task 4.1: User Authentication and Profiles
*   **Business Lens:** Necessary for user retention, monetization (freemium vs. pro tiers), and saving personalized data.
*   **Technical Lens:** Integrate a modern Auth provider (Supabase, Clerk, or FirebaseAuth). Secure API endpoints to require valid session tokens.

### Task 4.2: Portfolio Management Integration
*   **Business Lens:** Deepens user engagement. The AI is much more useful if it knows what the user currently holds.
*   **Technical Lens:** Build CRUD endpoints for portfolio holdings. Update the LLM context injector so the agents are "aware" of the user's portfolio when answering queries (e.g., "How does this news affect my portfolio?").

### Task 4.3: Persistent Long-Term Memory
*   **Business Lens:** Makes the AI feel like a dedicated financial advisor who remembers past conversations, risk tolerance, and investment goals.
*   **Technical Lens:** Upgrade from `MemorySaver` (short-term thread memory) to a robust vector database (Pinecone, Weaviate, or pgvector). Store user preferences, past analyses, and portfolio goals for long-term RAG (Retrieval-Augmented Generation) ingestion.

---

## Phase 5: Proactive Intelligence & Ecosystem Expansion
**Objective:** Move from a reactive system (user asks a question) to a proactive system (system alerts the user to opportunities).

### Task 5.1: Asynchronous Alerting Engine
*   **Business Lens:** Drives daily active usage (DAU). Users rely on the platform to monitor the market for them.
*   **Technical Lens:** Implement background workers (Celery, Redis Queue, or cron jobs) that periodically run specialized agents on the user's watchlist. If a significant event occurs (e.g., RSI crossover, major news), trigger an email, SMS, or push notification.

### Task 5.2: Automated Strategy Execution (Future / Advanced)
*   **Business Lens:** The ultimate value proposition: automated trading based on AI sentiment and technical analysis. *Note: High regulatory and risk implications.*
*   **Technical Lens:** Integrate with broker APIs (Alpaca, Interactive Brokers). Build a secure, user-approved execution pipeline where the agent can *suggest* trades that the user can execute with one click.

### Task 5.3: Market-Wide Scanning
*   **Business Lens:** Helps users discover *new* ideas rather than just analyzing stocks they already know.
*   **Technical Lens:** Build a daily cron job that uses the agents to scan the entire S&P 500 or Nasdaq 100 based on specific criteria (e.g., "Find all tech companies with P/E < 20 and positive news sentiment"). Surface these as a "Daily Insights" dashboard.
