import uuid
import pytest
from httpx import ASGITransport, AsyncClient
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app
from app.cache import set_cache, get_valkey_client

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
        "email": f"test_portlink_{run_id}@example.com",
        "password": "SecurePassword123!",
        "name": "Portfolio Tester"
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
async def test_portfolio_linking_and_goal_tracking(unique_user):
    valkey = get_valkey_client()
    await valkey.delete("live_price:AAPL")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Authenticate
            headers = await get_auth_headers(client, unique_user)

            # 2. Get portfolios (this creates a default "My Portfolio" which is standalone)
            res_list = await client.get("/api/portfolio", headers=headers)
            assert res_list.status_code == 200
            portfolios = res_list.json()
            assert len(portfolios) == 1
            default_port = portfolios[0]
            assert default_port["name"] == "My Portfolio"
            assert default_port["account_id"] is None
            assert default_port["account_name"] is None

            # 3. Create a portfolio account
            port_acc_payload = {
                "name": "HSBC Brokerage",
                "classification": "asset",
                "account_class": "portfolio",
                "balance": 0.0,
                "currency": "USD",
                "description": "Brokerage account"
            }
            res_create_acc = await client.post("/api/finance/accounts", json=port_acc_payload, headers=headers)
            assert res_create_acc.status_code == 200
            acc_data = res_create_acc.json()
            acc_id = acc_data["id"]

            # 4. Create a standalone portfolio
            res_create_port = await client.post(
                "/api/portfolio",
                json={"name": "Speculative Bets"},
                headers=headers
            )
            assert res_create_port.status_code == 200
            new_port_data = res_create_port.json()
            new_port_id = new_port_data["id"]
            assert new_port_data["name"] == "Speculative Bets"
            assert new_port_data["account_id"] is None

            # 5. Link "Speculative Bets" to the HSBC Brokerage account
            res_link = await client.patch(
                f"/api/portfolio/{new_port_id}",
                json={"account_id": acc_id},
                headers=headers
            )
            assert res_link.status_code == 200
            assert res_link.json()["status"] == "success"

            # 6. Verify link details on GET /api/portfolio/{id}
            res_get = await client.get(f"/api/portfolio/{new_port_id}", headers=headers)
            assert res_get.status_code == 200
            get_data = res_get.json()
            assert get_data["account_id"] == acc_id
            assert get_data["account_name"] == "HSBC Brokerage"

            # 7. Unlink the portfolio using sentinel -1
            res_unlink = await client.patch(
                f"/api/portfolio/{new_port_id}",
                json={"account_id": -1},
                headers=headers
            )
            assert res_unlink.status_code == 200
            
            # Verify it is unlinked now
            res_get_unlinked = await client.get(f"/api/portfolio/{new_port_id}", headers=headers)
            assert res_get_unlinked.status_code == 200
            unlinked_data = res_get_unlinked.json()
            assert unlinked_data["account_id"] is None
            assert unlinked_data["account_name"] is None

            # 8. Test live stock market pricing for goals
            # Add a holding of AAPL (10 shares @ 150 cost basis)
            res_add_holding = await client.post(
                f"/api/portfolio/{new_port_id}/holdings",
                json={
                    "ticker": "AAPL",
                    "shares": 10.0,
                    "avg_cost_basis": 150.0
                },
                headers=headers
            )
            assert res_add_holding.status_code == 200

            # Cache live price of AAPL to 200.0 (total live value 10 * 200 = 2000)
            # Cost basis total is 10 * 150 = 1500
            await set_cache("live_price:AAPL", "200.0")

            # Create a financial goal linked to the speculative bets portfolio
            goal_payload = {
                "title": "Tesla/Apple Fund",
                "category": "retirement",
                "target_amount": 3000.0,
                "target_date": "2030-01-01T00:00:00Z",
                "linked_asset_type": "portfolio",
                "linked_asset_id": new_port_id
            }
            res_create_goal = await client.post("/api/finance/goals", json=goal_payload, headers=headers)
            assert res_create_goal.status_code == 200
            goal_id = res_create_goal.json()["id"]

            # Fetch goals and verify that the progress uses the cached live price ($2000) instead of the cost basis ($1500)
            res_goals = await client.get("/api/finance/goals", headers=headers)
            assert res_goals.status_code == 200
            goals = res_goals.json()
            assert len(goals) > 0
            target_goal = next(g for g in goals if g["id"] == goal_id)
            
            # Verify saved amount is based on live price (10 * 200 = 2000)
            assert target_goal["total_saved"] == 2000.0
            # Progress percent = (2000 / 3000) * 100 = 66.666...%
            assert abs(target_goal["progress_percent"] - 66.67) < 0.1
    finally:
        await valkey.delete("live_price:AAPL")

