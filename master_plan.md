# Master Plan: The 360° Agentic Stock Analyzer Platform

This roadmap defines the evolution of the platform from a simple charting tool into a comprehensive, professional-grade equity research terminal. The goal is to provide users with a complete, immediate picture of a business's health—blending hard technicals, deep fundamentals, strategy simulations, and real-time qualitative data (news & filings) into a single pane of glass.

> [!IMPORTANT]
> **Core Constraint 1 (Open Source):** All implementations must rely strictly on **100% Free and Open Source Software (FOSS)** and free-tier APIs. We will not use paid data providers, closed-source charting libraries, or premium API keys to keep the project completely free to run and maintain for anyone.
> 
> **Core Constraint 2 (Resilient AI):** Every LLM call across the platform (whether for Sentiment, Fundamentals, or SEC Extraction) MUST use the centralized `get_llm()` fallback logic instituted in Phase 5. Primary routing will always attempt the free Gemini tier (`gemini-2.5-flash`), with an automatic, silent failover to Groq (`llama-3.3-70b-versatile`) if rate limits are hit.

---

## 1. Foundation: The Technical & Strategic Terminal
*Goal: Provide a flawless visual canvas for price action and historical backtesting.*

*   **1.1 Advanced Interactive Charting:** Upgrade the main price chart (e.g., via Lightweight Charts) to support seamless zooming, panning, and toggling between Candlesticks, Lines, and varying timeframes (1D to Max).
*   **1.2 Native Technical Overlays & Oscillators:** Empower users to manually layer on indicators (SMA, EMA, Bollinger Bands) and dedicated oscillators (RSI, MACD, Volume) with a customizable UI panel.
*   **1.3 Strategy Simulation Engine:** Connect the UI's Strategy Builder to the backend `/api/backtest` engine. Visualize the resulting Equity Curve, display key performance metrics (Max Drawdown, Win Rate), and plot historical Buy/Sell execution markers directly onto the candlestick chart.

## 2. The Qualitative Engine: News & Market Sentiment
*Goal: Surface real-time human reaction and broader market context alongside the numbers.*

*   **2.1 Real-Time News Aggregation:** Integrate a high-quality, free news API (e.g., DuckDuckGo web search scraping, or Yahoo Finance News RSS) to pull the top 10 most recent articles for the active ticker.
*   **2.2 AI-Powered Sentiment Summaries:** Instead of just listing headlines, use the free-tier LLM configuration (Gemini Flash / Groq) to briefly synthesize the overarching narrative from those 10 articles.
*   **2.3 Macro Economic Calendar (Future):** Display upcoming earnings dates, dividend ex-dates, and major Fed announcements that could impact the ticker's price action.

## 3. The Quantitative Engine: Deep Fundamentals
*Goal: Dig below the price action to understand the actual business model and its financial health.*

*   **3.1 Fundamental Highlights Dashboard:** Instantly display core metrics (P/E, Forward P/E, Market Cap, Debt-to-Equity, PEG ratio, Dividend Yield).
*   **3.2 AI Business & Competitor Analysis:** Utilize the existing LLM pipelines to generate the "Business Model Story", "Porter's 5 Forces", and direct "Competitor Comparisons".
*   **3.3 Financial Statement Visualization:** Pull historical Income Statements, Balance Sheets, and Cash Flows (via yfinance) and render them as mini bar-charts (e.g., visualizing Revenue Growth vs. Net Income over the last 4 quarters).

## 4. The Institutional Edge: SEC Filings & Primary Sources
*Goal: Give retail investors the same primary source data that institutional analysts use.*

*   **4.1 10-K/10-Q Ingestion (Active Work):** Finalize the integration of `edgartools` to pull the raw text of the most recent annual and quarterly filings.
*   **4.2 "Management Discussion" Extraction:** Use the LLM to specifically isolate, read, and summarize the "Management's Discussion and Analysis" (MD&A) section and the "Risk Factors" section from the latest 10-K. 
*   **4.3 Insider Trading Logs:** Display recent Form 4 filings to track whether C-Suite executives are buying or dumping their own stock.

## 5. Personalization & Platform Maturation
*Goal: Transform the tool from a stateless search engine into a personalized workspace.*

*   **5.1 Watchlists & Screeners:** Allow users to save tickers. Build a basic screener to filter the market by technicals (e.g., "RSI < 30") or fundamentals (e.g., "P/E < 15").
*   **5.2 Saved Workspaces:** Allow users to save their specific chart indicator setups and backtest strategy rules to their local browser profile.
