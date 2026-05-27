import uuid
import pytest
from httpx import ASGITransport, AsyncClient
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app
from app.database import async_session
from app.models import Account, AccountTransaction
from sqlalchemy import select

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
        "email": f"test_ledger_{run_id}@example.com",
        "password": "SecurePassword123!",
        "name": "Ledger Tester"
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
async def test_ledger_transactions_and_transfers(unique_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Authenticate user
        headers = await get_auth_headers(client, unique_user)

        # 2. Add source cash account (HSBC Savings) with initial balance 1000.0 GBP
        hsbc_payload = {
            "name": "HSBC Savings",
            "classification": "asset",
            "account_class": "cash",
            "balance": 1000.0,
            "currency": "GBP",
            "description": "UK Savings"
        }
        res_hsbc = await client.post("/api/finance/accounts", json=hsbc_payload, headers=headers)
        assert res_hsbc.status_code == 200
        hsbc_id = res_hsbc.json()["id"]

        # 3. Add destination account (Chase CC) with initial balance 0.0 USD
        chase_payload = {
            "name": "Chase CC",
            "classification": "liability",
            "account_class": "credit_card",
            "balance": 0.0,
            "currency": "USD",
            "description": "Credit Card"
        }
        res_chase = await client.post("/api/finance/accounts", json=chase_payload, headers=headers)
        assert res_chase.status_code == 200
        chase_id = res_chase.json()["id"]

        # 4. Log a standard transaction (debit/expense) on HSBC: -50.0 GBP
        tx_payload = {
            "amount": -50.0,
            "transaction_type": "expense",
            "category": "Food",
            "description": "Weekly Groceries",
            "date": datetime.now(timezone.utc).isoformat()
        }
        res_tx = await client.post(f"/api/finance/accounts/{hsbc_id}/transactions", json=tx_payload, headers=headers)
        assert res_tx.status_code == 200
        tx_data = res_tx.json()
        assert tx_data["amount"] == -50.0
        tx_id = tx_data["id"]

        # Check that account balance decreased automatically: 1000.0 - 50.0 = 950.0 GBP
        res_acc_check = await client.get("/api/finance/accounts", headers=headers)
        hsbc_data = next(a for a in res_acc_check.json() if a["id"] == hsbc_id)
        assert hsbc_data["balance"] == 950.0

        # 5. Update transaction amount: change -50.0 to -70.0 GBP
        update_payload = {
            "amount": -70.0
        }
        res_update = await client.patch(f"/api/finance/accounts/{hsbc_id}/transactions/{tx_id}", json=update_payload, headers=headers)
        assert res_update.status_code == 200
        assert res_update.json()["amount"] == -70.0

        # Check account balance: 1000.0 - 70.0 = 930.0 GBP
        res_acc_check_2 = await client.get("/api/finance/accounts", headers=headers)
        hsbc_data_2 = next(a for a in res_acc_check_2.json() if a["id"] == hsbc_id)
        assert hsbc_data_2["balance"] == 930.0

        # 6. Execute internal transfer: transfer 200 GBP from HSBC Savings to Chase CC
        transfer_payload = {
            "from_account_id": hsbc_id,
            "to_account_id": chase_id,
            "amount": 200.0,
            "description": "CC Payment",
            "date": datetime.now(timezone.utc).isoformat()
        }
        res_transfer = await client.post("/api/finance/accounts/transfer", json=transfer_payload, headers=headers)
        assert res_transfer.status_code == 200
        
        # Verify both accounts' balances have updated:
        # HSBC balance: 930.0 - 200.0 = 730.0 GBP
        # Chase balance: 0.0 + 200.0 = 200.0 USD
        res_acc_check_3 = await client.get("/api/finance/accounts", headers=headers)
        hsbc_data_3 = next(a for a in res_acc_check_3.json() if a["id"] == hsbc_id)
        chase_data_3 = next(a for a in res_acc_check_3.json() if a["id"] == chase_id)
        assert hsbc_data_3["balance"] == 730.0
        assert chase_data_3["balance"] == 200.0

        # Verify both transactions exist in the database and are linked
        res_txs_hsbc = await client.get(f"/api/finance/accounts/{hsbc_id}/transactions", headers=headers)
        assert len(res_txs_hsbc.json()) == 2 # groceries and transfer_out
        tx_out = next(t for t in res_txs_hsbc.json() if t["transaction_type"] == "transfer_out")
        assert tx_out["amount"] == -200.0
        assert tx_out["transfer_linked_transaction_id"] is not None

        # 7. Delete transfer_out transaction - this should automatically cascade delete the linked transfer_in transaction on Chase,
        # restoring both account balances:
        # HSBC: 730.0 + 200.0 = 930.0 GBP
        # Chase: 200.0 - 200.0 = 0.0 USD
        res_del = await client.delete(f"/api/finance/accounts/{hsbc_id}/transactions/{tx_out['id']}", headers=headers)
        assert res_del.status_code == 200

        res_acc_check_4 = await client.get("/api/finance/accounts", headers=headers)
        hsbc_data_4 = next(a for a in res_acc_check_4.json() if a["id"] == hsbc_id)
        chase_data_4 = next(a for a in res_acc_check_4.json() if a["id"] == chase_id)
        assert hsbc_data_4["balance"] == 930.0
        assert chase_data_4["balance"] == 0.0
        
        # Verify transfer_in transaction is gone
        res_txs_chase = await client.get(f"/api/finance/accounts/{chase_id}/transactions", headers=headers)
        assert len(res_txs_chase.json()) == 0
