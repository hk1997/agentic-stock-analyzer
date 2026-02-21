"""
Backend API Tests — Iteration 1 Quality Gate
Tests health endpoint, stock data endpoint, and SSE chat stream contract.
"""
import os
import sys

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.main import app  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health_endpoint():
    """Health endpoint should return 200 with status info."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "graph_ready" in data


@pytest.mark.anyio
async def test_stock_endpoint_valid_ticker():
    """Stock endpoint should return price data for a valid ticker."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/stock/AAPL?period=1mo")
    assert response.status_code == 200
    data = response.json()
    assert "ticker" in data
    assert data["ticker"] == "AAPL"
    # Should have either price data or a documented error
    if "error" not in data:
        assert "price" in data
        assert "history" in data
        assert isinstance(data["history"], list)


@pytest.mark.anyio
async def test_stock_endpoint_invalid_period():
    """Stock endpoint should reject invalid period values."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/stock/AAPL?period=invalid")
    assert response.status_code == 422  # Validation error


@pytest.mark.anyio
async def test_chat_sync_endpoint():
    """Synchronous chat endpoint should return a reply."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/chat",
            json={"message": "Hello", "thread_id": "test-1"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "thread_id" in data
    assert data["thread_id"] == "test-1"


@pytest.mark.anyio
async def test_chat_stream_returns_sse():
    """SSE chat stream should return text/event-stream content type."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/chat/stream",
            json={"message": "What is Apple's P/E ratio?", "thread_id": "test-sse-1"},
        )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.anyio
async def test_cors_headers():
    """CORS should allow requests from localhost:5173."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    # Should not be 405 Method Not Allowed
    assert response.status_code in (200, 204)
    assert "access-control-allow-origin" in response.headers
