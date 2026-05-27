import uuid
import pytest
from httpx import ASGITransport, AsyncClient
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app

@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture(autouse=True, scope="module")
async def init_test_db():
    from app.models import Base
    from app.database import engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

@pytest.fixture
def unique_user():
    run_id = str(uuid.uuid4())[:8]
    return {
        "email": f"test_accounts_{run_id}@example.com",
        "password": "SecurePassword123!",
        "name": "Account Tester"
    }

async def get_auth_headers(client: AsyncClient, credentials: dict) -> dict:
    reg_res = await client.post("/api/auth/register", json=credentials)
    assert reg_res.status_code == 200
    
    log_res = await client.post("/api/auth/login", data={
        "username": credentials["email"],
        "password": credentials["password"]
    })
    assert log_res.status_code == 200
    token = log_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.anyio
async def test_accounts_crud_and_net_worth(unique_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Authenticate user
        headers = await get_auth_headers(client, unique_user)

        # 2. Add an asset account: HSBC Savings in GBP (£)
        hsbc_payload = {
            "name": "HSBC Savings",
            "classification": "asset",
            "account_class": "cash",
            "balance": 1000.0,
            "currency": "GBP",
            "description": "UK Savings"
        }
        res_create_hsbc = await client.post("/api/finance/accounts", json=hsbc_payload, headers=headers)
        assert res_create_hsbc.status_code == 200
        hsbc_data = res_create_hsbc.json()
        assert hsbc_data["name"] == "HSBC Savings"
        assert hsbc_data["balance"] == 1000.0
        assert hsbc_data["currency"] == "GBP"
        assert hsbc_data["balance_usd"] > 1000.0
        hsbc_id = hsbc_data["id"]

        # 3. Add a liability account: Credit Card in USD ($)
        cc_payload = {
            "name": "Chase Credit Card",
            "classification": "liability",
            "account_class": "credit_card",
            "balance": 300.0,
            "currency": "USD",
            "description": "Monthly spend"
        }
        res_create_cc = await client.post("/api/finance/accounts", json=cc_payload, headers=headers)
        assert res_create_cc.status_code == 200
        cc_data = res_create_cc.json()
        assert cc_data["name"] == "Chase Credit Card"
        assert cc_data["balance_usd"] == 300.0
        cc_id = cc_data["id"]

        # 4. Fetch accounts list
        res_list = await client.get("/api/finance/accounts", headers=headers)
        assert res_list.status_code == 200
        accounts = res_list.json()
        assert len(accounts) == 2
        names = [a["name"] for a in accounts]
        assert "HSBC Savings" in names
        assert "Chase Credit Card" in names

        # 5. Fetch net worth history and verify calculation: 
        # Net Worth = Converted Assets (HSBC Savings) - Converted Liabilities (Chase CC)
        res_nw = await client.get("/api/finance/net-worth-history", headers=headers)
        assert res_nw.status_code == 200
        nw_history = res_nw.json()
        assert len(nw_history) >= 1
        live_net_worth = nw_history[-1]["net_worth"]
        
        # Converted HSBC - Chase CC using actual converted balances
        hsbc_usd = next(a["balance_usd"] for a in accounts if a["id"] == hsbc_id)
        cc_usd = next(a["balance_usd"] for a in accounts if a["id"] == cc_id)
        expected_nw = hsbc_usd - cc_usd
        assert abs(live_net_worth - expected_nw) < 1.0

        # 6. Test dynamic Portfolio Account link and rollup
        port_acc_payload = {
            "name": "Trading 212 Portfolio",
            "classification": "asset",
            "account_class": "portfolio",
            "balance": 0.0,
            "currency": "USD",
            "description": "Brokerage stocks"
        }
        res_create_port_acc = await client.post("/api/finance/accounts", json=port_acc_payload, headers=headers)
        assert res_create_port_acc.status_code == 200
        port_acc_id = res_create_port_acc.json()["id"]

        # Retrieve the auto-created child portfolio
        res_port_list = await client.get("/api/portfolio", headers=headers)
        assert res_port_list.status_code == 200
        portfolios = res_port_list.json()
        # Find portfolio linked to our account
        portfolio_id = portfolios[0]["id"] # Since we cleaned db, this is the main portfolio

        # Add a stock holding to this portfolio: AAPL (10 shares @ 150) = 1500 USD
        res_add_holding = await client.post(
            f"/api/portfolio/{portfolio_id}/holdings",
            json={
                "ticker": "AAPL",
                "shares": 10.0,
                "avg_cost_basis": 150.0
            },
            headers=headers
        )
        assert res_add_holding.status_code == 200

        # Fetch accounts again - Trading 212 balance should dynamically sum up to 1500 USD!
        res_list_dynamic = await client.get("/api/finance/accounts", headers=headers)
        port_acc_data = next(a for a in res_list_dynamic.json() if a["id"] == port_acc_id)
        assert port_acc_data["balance"] == 1500.0
        assert port_acc_data["balance_usd"] == 1500.0

        # 7. Update Account Details
        res_patch = await client.patch(
            f"/api/finance/accounts/{hsbc_id}", 
            json={"balance": 2000.0},
            headers=headers
        )
        assert res_patch.status_code == 200
        patched_data = res_patch.json()
        assert patched_data["balance"] == 2000.0

        # Verify updated Net Worth
        res_nw_updated = await client.get("/api/finance/net-worth-history", headers=headers)
        assert res_nw_updated.json()[-1]["net_worth"] > live_net_worth

        # 8. Test linking account to a financial goal
        target_date = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        goal_payload = {
            "title": "Retirement Fund",
            "category": "Emergency Fund",
            "target_amount": 10000.0,
            "target_date": target_date,
            "linked_asset_type": "account",
            "linked_asset_id": hsbc_id
        }
        res_create_goal = await client.post("/api/finance/goals", json=goal_payload, headers=headers)
        assert res_create_goal.status_code == 200
        goal_id = res_create_goal.json()["id"]

        # Fetch goal list and verify target tracking
        res_goals = await client.get("/api/finance/goals", headers=headers)
        goal_data = next(g for g in res_goals.json() if g["id"] == goal_id)
        assert goal_data["linked_asset_type"] == "account"
        assert goal_data["linked_asset_value"] > 2000.0
        assert goal_data["total_saved"] == goal_data["linked_asset_value"]

        # 9. Delete accounts
        res_del_cc = await client.delete(f"/api/finance/accounts/{cc_id}", headers=headers)
        assert res_del_cc.status_code == 200
        
        res_list_final = await client.get("/api/finance/accounts", headers=headers)
        # Should now contain HSBC Savings and Trading 212 Portfolio
        assert len(res_list_final.json()) == 2
