import uuid
import pytest
from httpx import ASGITransport, AsyncClient
import sys
import os
import datetime
from unittest.mock import MagicMock, patch

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
        "email": f"test_summary_{run_id}@example.com",
        "password": "SecurePassword123!",
        "name": "Test User"
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
async def test_send_monthly_summary(unique_user):
    from app.database import engine
    from app.models import User, Expense, Income, NetWorthSnapshot, FinancialGoal
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Authenticate user
        headers = await get_auth_headers(client, unique_user)
        
        # Get database session to seed data
        async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session_factory() as db:
            user_res = await db.execute(select(User).where(User.email == unique_user["email"]))
            user = user_res.scalar_one()
            user_id = user.id
            
            # Seed Income
            income1 = Income(owner_id=user_id, date=datetime.datetime(2026, 5, 15, tzinfo=datetime.timezone.utc), source="Salary", amount=5000.0)
            db.add(income1)
            
            # Seed Expense
            expense1 = Expense(owner_id=user_id, date=datetime.datetime(2026, 5, 10, tzinfo=datetime.timezone.utc), category="Food", amount=150.0, description="Sushi dinner")
            expense2 = Expense(owner_id=user_id, date=datetime.datetime(2026, 5, 20, tzinfo=datetime.timezone.utc), category="Rent", amount=1200.0, description="Apartment")
            db.add_all([expense1, expense2])
            
            # Seed Goal
            target_date = datetime.datetime(2027, 5, 1, tzinfo=datetime.timezone.utc)
            goal1 = FinancialGoal(owner_id=user_id, title="Save for Car", category="Car", target_amount=15000.0, target_date=target_date)
            db.add(goal1)
            
            # Seed Net Worth Snapshots
            # Previous month
            snap_prev = NetWorthSnapshot(owner_id=user_id, date=datetime.datetime(2026, 4, 30, tzinfo=datetime.timezone.utc), total_assets=20000.0, total_liabilities=5000.0)
            # Current month
            snap_curr = NetWorthSnapshot(owner_id=user_id, date=datetime.datetime(2026, 5, 28, tzinfo=datetime.timezone.utc), total_assets=25000.0, total_liabilities=4500.0)
            db.add_all([snap_prev, snap_curr])
            
            await db.commit()

        # Mock LLM and AgentMail
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="<html><body><h1>Test Monthly Summary HTML Content</h1></body></html>")
        
        mock_agentmail_instance = MagicMock()
        mock_agentmail_instance.inboxes.messages.send.return_value = MagicMock(message_id="test_msg_id_123")
        
        with patch("app.email_service.get_llm", return_value=mock_llm), \
             patch("agentmail.AgentMail", return_value=mock_agentmail_instance):
             
            # Hit endpoint to send monthly summary
            response = await client.post("/api/finance/send-monthly-summary?month=2026-05", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "recipient" in data
            assert data["month"] == "2026-05"
            
            # Verify AgentMail send was called
            mock_agentmail_instance.inboxes.messages.send.assert_called_once()
            call_kwargs = mock_agentmail_instance.inboxes.messages.send.call_args[1]
            assert call_kwargs["subject"] == "📊 Monthly Financial Summary — 2026-05"
            assert "<h1>Test Monthly Summary HTML Content</h1>" in call_kwargs["html"]
