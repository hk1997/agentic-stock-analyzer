# Rearchitecture Plan: Agentic Stock Analyzer

This document outlines the tasks required to resolve architectural gaps, latency issues, and vulnerabilities identified in the recent architectural review. The tasks are topologically sorted by priority, tackling critical bugs first, followed by UX improvements, and finally infrastructural robustness.

## 1. Eliminate State Leakage (Critical Priority)
**Task:** Implement Dynamic Thread UUIDs
**Description:** The React frontend currently hardcodes the `thread_id` to `'react-session-1'`. This causes all concurrent users to share the same LangGraph state, leading to cross-session data leakage and chaotic agent behavior. We need to generate a unique UUID per browser session.
**Tools & Implementation:**
- **Frontend (React):** Use the standard `crypto.randomUUID()` or the `uuid` npm package to generate a session ID when the app loads. Persist this in `sessionStorage` or local state.
- **Backend (FastAPI):** Ensure the backend respects the provided `thread_id` from the request payload.

## 2. Reduce Perceived Latency (High Priority)
**Task:** Implement Token-by-Token Streaming
**Description:** The UI currently waits for an entire node execution to complete before rendering the text block (due to `stream_mode="updates"`). This introduces a 5-15 second wait. We must stream tokens one-by-one to give immediate visual feedback.
**Tools & Implementation:**
- **Backend (LangGraph/FastAPI):** Switch to LangGraph's `astream_events` API (or `stream_mode="messages"`). This allows yielding `on_chat_model_stream` events token-by-token. Use `sse_starlette` to continuously pump these chunks to the client.
- **Frontend (React):** Parse the granular SSE chunks and append them to the existing message bubble in real-time.

## 3. Mitigate Hallucinations & Infinite Loops (High Priority)
**Task:** Enforce Hallucination Guardrails & Supervisor Constraints
**Description:** The Supervisor graph can loop indefinitely and lacks the mechanism to reject off-topic questions. We will introduce an Intent Classifier node at the entry point and strictly constrain the Supervisor's routing behavior.
**Tools & Implementation:**
- **LangChain/LangGraph:** Add an `IntentClassifier` node using `with_structured_output` (powered by Pydantic schemas) to validate if a query is financial BEFORE passing it to the Supervisor.
- **Graph Edges:** Explicitly constrain the conditionally returned edges. If an analyst completes its task, force an evaluation step that mandates a termination (`FINISH`) instead of indiscriminately looping back.

## 4. Ensure Production State Resilience (Medium Priority)
**Task:** Transition to Persistent Checkpointing
**Description:** `MemorySaver()` operates strictly in-memory. If the Fastapi server restarts, scales up to multiple workers, or runs in Docker, conversation history vanishes.
**Tools & Implementation:**
- **LangGraph Checkpoint:** Replace `MemorySaver` with `SqliteSaver` (for local dev) or `AsyncPostgresSaver` (for production). This ensures that thread states are serialized into a database.
- **Dependencies:** `langgraph-checkpoint-sqlite` or `langgraph-checkpoint-postgres`.

## 5. Optimize Synchronous Bottlenecks (Medium Priority)
**Task:** Mitigate `yfinance` Thread Exhaustion
**Description:** The `/api/stock/{ticker}` endpoint uses `asyncio.to_thread` for `yfinance` calls. While this avoids completely blocking the main thread, high concurrent traffic will exhaust the default thread pool, slowing down the ASGI server.
**Tools & Implementation:**
- **FastAPI / Async:** Replace `yfinance` blocking calls where possible by calling the underlying Yahoo Finance REST APIs asynchronously with `httpx`. Alternatively, manage a dedicated `ThreadPoolExecutor` strictly for standard `yfinance` calls with explicit worker limits.

---
**Execution Note**: Tasks 1 and 2 should be executed immediately to provide the most visible stability and performance benefits.
