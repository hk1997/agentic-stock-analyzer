import uuid
import pytest
from fastapi.testclient import TestClient

import sys
import os
import contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from api.main import app

# Override the lifespan to prevent it from launching background tasks (like yfinance or APScheduler) that hang in the sandbox.
@contextlib.asynccontextmanager
async def mock_lifespan(app: FastAPI):
    yield

app.router.lifespan_context = mock_lifespan

client = TestClient(app)

@pytest.fixture(scope="module")
def unique_users():
    """Generates two unique emails and a standard password for the test suite."""
    run_id = str(uuid.uuid4())[:8]
    return {
        "user_a_email": f"test_a_{run_id}@example.com",
        "user_b_email": f"test_b_{run_id}@example.com",
        "password": "SecurePassword123!"
    }

def test_e2e_super_app_flow(unique_users):
    """
    End-to-End Test for the Financial Super App.
    Tests Auth, Account Linking, Expenses, Net Worth, and Unified Portfolios.
    """
    
    # ---------------------------------------------------------
    # 1. Authentication Flow
    # ---------------------------------------------------------
    
    # Register User A
    res_a_reg = client.post("/api/auth/register", json={
        "email": unique_users["user_a_email"],
        "password": unique_users["password"],
        "name": "User A"
    })
    assert res_a_reg.status_code == 200, f"Register A failed: {res_a_reg.text}"
    
    # Login User A
    res_a_log = client.post("/api/auth/login", json={
        "email": unique_users["user_a_email"],
        "password": unique_users["password"]
    })
    assert res_a_log.status_code == 200, f"Login A failed: {res_a_log.text}"
    token_a = res_a_log.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Register User B
    res_b_reg = client.post("/api/auth/register", json={
        "email": unique_users["user_b_email"],
        "password": unique_users["password"],
        "name": "User B"
    })
    assert res_b_reg.status_code == 200, f"Register B failed: {res_b_reg.text}"

    # Login User B
    res_b_log = client.post("/api/auth/login", json={
        "email": unique_users["user_b_email"],
        "password": unique_users["password"]
    })
    assert res_b_log.status_code == 200, f"Login B failed: {res_b_log.text}"
    token_b = res_b_log.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Verify /me endpoint
    me_res = client.get("/api/auth/me", headers=headers_a)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == unique_users["user_a_email"]

    # ---------------------------------------------------------
    # 2. Account Linking Flow
    # ---------------------------------------------------------
    
    # User A links with User B
    link_res = client.post("/api/auth/link-account", json={"target_email": unique_users["user_b_email"]}, headers=headers_a)
    assert link_res.status_code == 200, f"Link account failed: {link_res.text}"
    
    # Verify User B is in User A's linked accounts
    linked_res = client.get("/api/auth/linked-accounts", headers=headers_a)
    assert linked_res.status_code == 200
    linked_data = linked_res.json()
    assert len(linked_data) == 1
    assert linked_data[0]["email"] == unique_users["user_b_email"]

    # ---------------------------------------------------------
    # 3. Expense Management Flow
    # ---------------------------------------------------------
    
    # User A adds a personal expense
    exp1_res = client.post("/api/finance/expenses", json={
        "date": "2023-10-01T00:00:00Z",
        "category": "Food",
        "amount": 50.0,
        "description": "Lunch",
        "is_joint": False
    }, headers=headers_a)
    assert exp1_res.status_code == 200

    # User A adds a joint expense
    exp2_res = client.post("/api/finance/expenses", json={
        "date": "2023-10-02T00:00:00Z",
        "category": "Utilities",
        "amount": 100.0,
        "description": "Electric Bill",
        "is_joint": True
    }, headers=headers_a)
    assert exp2_res.status_code == 200

    # Verify expenses are retrieved
    exp_get_res = client.get("/api/finance/expenses", headers=headers_a)
    assert exp_get_res.status_code == 200
    exp_data = exp_get_res.json()
    assert len(exp_data) == 2
    categories = [e["category"] for e in exp_data]
    assert "Food" in categories
    assert "Utilities" in categories

    # ---------------------------------------------------------
    # 4. Net Worth & Manual Assets Flow
    # ---------------------------------------------------------
    
    # User A adds a manual asset
    ma_res = client.post("/api/finance/manual-assets", json={
        "asset_type": "cash",
        "name": "Checking Account",
        "value": 5000.0
    }, headers=headers_a)
    assert ma_res.status_code == 200

    # Fetch net worth history, this should trigger a calculation including the manual asset
    nw_res = client.get("/api/finance/net-worth-history", headers=headers_a)
    assert nw_res.status_code == 200
    nw_data = nw_res.json()
    
    # Note: If no previous snapshots existed for this new user, this endpoint returns the current live snapshot
    assert len(nw_data) >= 1
    # Check if the manual asset is accounted for (value >= 5000)
    assert nw_data[-1]["net_worth"] >= 5000.0

    # ---------------------------------------------------------
    # 5. Unified Portfolio Flow
    # ---------------------------------------------------------
    
    # First, User A creates a portfolio (or uses default if auto-created, but our API creates one on demand usually or they have to create one)
    # Let's see if User A has a portfolio
    port_a_list = client.get("/api/portfolio", headers=headers_a)
    if not port_a_list.json():
        # Create one if not exists
        client.post("/api/portfolio", json={"name": "A's Portfolio"}, headers=headers_a)
        port_a_list = client.get("/api/portfolio", headers=headers_a)
    port_a_id = port_a_list.json()[0]["id"]

    # User A adds AAPL
    add_aapl = client.post(f"/api/portfolio/{port_a_id}/holdings", json={
        "ticker": "AAPL",
        "shares": 10,
        "avg_cost_basis": 150.0
    }, headers=headers_a)
    assert add_aapl.status_code == 200

    # User B creates a portfolio and adds MSFT
    port_b_list = client.get("/api/portfolio", headers=headers_b)
    if not port_b_list.json():
        client.post("/api/portfolio", json={"name": "B's Portfolio"}, headers=headers_b)
        port_b_list = client.get("/api/portfolio", headers=headers_b)
    port_b_id = port_b_list.json()[0]["id"]

    add_msft = client.post(f"/api/portfolio/{port_b_id}/holdings", json={
        "ticker": "MSFT",
        "shares": 5,
        "avg_cost_basis": 250.0
    }, headers=headers_b)
    assert add_msft.status_code == 200

    # Fetch Unified Portfolio as User A
    unified_res = client.get("/api/finance/unified-portfolio", headers=headers_a)
    assert unified_res.status_code == 200
    unified_data = unified_res.json()

    # Unified Portfolio should contain both AAPL (from User A) and MSFT (from User B linked to A)
    tickers = [h["ticker"] for h in unified_data["holdings"]]
    assert "AAPL" in tickers, "User A's holdings are missing from unified view"
    assert "MSFT" in tickers, "Linked User B's holdings are missing from unified view"

    # Total cost should be 10 * 150 + 5 * 250 = 1500 + 1250 = 2750
    assert unified_data["total_cost"] == 2750.0

    print("✅ All E2E flows verified successfully!")
