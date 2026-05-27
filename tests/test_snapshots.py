import uuid
import pytest
from httpx import ASGITransport, AsyncClient
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app
from app.database import async_session
from app.models import NetWorthSnapshot
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
        "email": f"test_snapshots_{run_id}@example.com",
        "password": "SecurePassword123!",
        "name": "Snapshot Tester"
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
async def test_snapshots_and_resolution(unique_user):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Authenticate user
        headers = await get_auth_headers(client, unique_user)

        # Get user ID from database
        async with async_session() as db:
            from app.models import User
            res = await db.execute(select(User.id).where(User.email == unique_user["email"]))
            user_id = res.scalar()

        # 2. Add an account so net worth is non-zero
        acc_payload = {
            "name": "Savings Account",
            "classification": "asset",
            "account_class": "cash",
            "balance": 5000.0,
            "currency": "USD",
            "description": "Savings"
        }
        res_acc = await client.post("/api/finance/accounts", json=acc_payload, headers=headers)
        assert res_acc.status_code == 200

        # 3. Fetch history - this should lazy-trigger today's snapshot creation
        res_hist_1 = await client.get("/api/finance/net-worth-history?resolution=daily", headers=headers)
        assert res_hist_1.status_code == 200
        history_1 = res_hist_1.json()
        assert len(history_1) == 1
        assert history_1[0]["net_worth"] == 5000.0
        assert history_1[0]["is_live"] is True

        # Verify today's snapshot was written to DB
        async with async_session() as db:
            db_res = await db.execute(select(NetWorthSnapshot).where(NetWorthSnapshot.owner_id == user_id))
            snapshots = db_res.scalars().all()
            assert len(snapshots) == 1
            assert snapshots[0].total_assets == 5000.0
            assert snapshots[0].total_liabilities == 0.0

        # 4. Insert historical snapshots to test monthly resolution aggregation
        two_months_ago = datetime.now(timezone.utc) - timedelta(days=60)
        one_month_ago_early = datetime.now(timezone.utc) - timedelta(days=32)
        one_month_ago_late = datetime.now(timezone.utc) - timedelta(days=30)

        async with async_session() as db:
            snap1 = NetWorthSnapshot(
                owner_id=user_id,
                date=datetime(two_months_ago.year, two_months_ago.month, two_months_ago.day, tzinfo=timezone.utc),
                total_assets=3000.0,
                total_liabilities=500.0 # NW: 2500
            )
            snap2 = NetWorthSnapshot(
                owner_id=user_id,
                date=datetime(one_month_ago_early.year, one_month_ago_early.month, one_month_ago_early.day, tzinfo=timezone.utc),
                total_assets=4000.0,
                total_liabilities=500.0 # NW: 3500
            )
            snap3 = NetWorthSnapshot(
                owner_id=user_id,
                date=datetime(one_month_ago_late.year, one_month_ago_late.month, one_month_ago_late.day, tzinfo=timezone.utc),
                total_assets=4500.0,
                total_liabilities=500.0 # NW: 4000
            )
            db.add_all([snap1, snap2, snap3])
            await db.commit()

        # 5. Fetch daily resolution (should return all 4 snapshots)
        res_daily = await client.get("/api/finance/net-worth-history?resolution=daily", headers=headers)
        assert res_daily.status_code == 200
        daily_data = res_daily.json()
        assert len(daily_data) == 4
        # Ordered by date ascending
        assert daily_data[0]["net_worth"] == 2500.0
        assert daily_data[1]["net_worth"] == 3500.0
        assert daily_data[2]["net_worth"] == 4000.0
        assert daily_data[3]["net_worth"] == 5000.0

        # 6. Fetch monthly resolution (should group snap2 and snap3 into the latest one, i.e., snap3)
        res_monthly = await client.get("/api/finance/net-worth-history?resolution=monthly", headers=headers)
        assert res_monthly.status_code == 200
        monthly_data = res_monthly.json()
        assert len(monthly_data) == 3
        
        # Verify values:
        assert monthly_data[0]["net_worth"] == 2500.0
        assert monthly_data[1]["net_worth"] == 4000.0
        assert monthly_data[2]["net_worth"] == 5000.0
