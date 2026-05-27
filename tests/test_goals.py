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
def unique_users():
    run_id = str(uuid.uuid4())[:8]
    return {
        "user_a": {
            "email": f"test_goals_a_{run_id}@example.com",
            "password": "SecurePassword123!",
            "name": "Alex User"
        },
        "user_b": {
            "email": f"test_goals_b_{run_id}@example.com",
            "password": "SecurePassword123!",
            "name": "Sam User"
        }
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
async def test_joint_goals_workflow(unique_users):
    from app.database import engine
    from app.models import User, LinkedAccount, ManualAsset
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Authenticate users
        headers_a = await get_auth_headers(client, unique_users["user_a"])
        headers_b = await get_auth_headers(client, unique_users["user_b"])

        # Get database session to manually link users and fetch IDs
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            user_a_res = await db.execute(select(User).where(User.email == unique_users["user_a"]["email"]))
            user_a = user_a_res.scalar_one()
            
            user_b_res = await db.execute(select(User).where(User.email == unique_users["user_b"]["email"]))
            user_b = user_b_res.scalar_one()

            # Create symmetrical links
            link_a_to_b = LinkedAccount(user_id=user_a.id, linked_user_id=user_b.id)
            link_b_to_a = LinkedAccount(user_id=user_b.id, linked_user_id=user_a.id)
            db.add_all([link_a_to_b, link_b_to_a])
            await db.commit()

        # 2. User A creates a joint goal for buying a house
        target_date = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        goal_payload = {
            "title": "Buy a House",
            "category": "House",
            "target_amount": 100000.0,
            "target_date": target_date,
            "income_sources": "Salary, Bonus",
            "cash_flows": '[{"id":"1","owner":"You","type":"continuous","amount":500.0,"label":"Salary Allocation"}]'
        }
        create_res = await client.post("/api/finance/goals", json=goal_payload, headers=headers_a)
        assert create_res.status_code == 200
        goal_data = create_res.json()
        goal_id = goal_data["id"]
        assert goal_data["title"] == "Buy a House"
        assert goal_data["target_amount"] == 100000.0
        assert goal_data["income_sources"] == "Salary, Bonus"
        assert goal_data["cash_flows"] == '[{"id":"1","owner":"You","type":"continuous","amount":500.0,"label":"Salary Allocation"}]'

        # 3. User B fetches goals - the joint goal should show up because they are linked
        get_res_b = await client.get("/api/finance/goals", headers=headers_b)
        assert get_res_b.status_code == 200
        goals_b = get_res_b.json()
        assert len(goals_b) == 1
        assert goals_b[0]["id"] == goal_id
        assert goals_b[0]["owner_name"] == "Alex User"  # User A's name

        # 4. User A adds a contribution of $5,000
        contrib_res_a = await client.post(
            f"/api/finance/goals/{goal_id}/contributions",
            json={"amount": 5000.0, "description": "Alex first save"},
            headers=headers_a
        )
        assert contrib_res_a.status_code == 200
        contrib_a_id = contrib_res_a.json()["id"]

        # 5. User B adds a contribution of $3,000
        contrib_res_b = await client.post(
            f"/api/finance/goals/{goal_id}/contributions",
            json={"amount": 3000.0, "description": "Sam contribution"},
            headers=headers_b
        )
        assert contrib_res_b.status_code == 200
        contrib_b_id = contrib_res_b.json()["id"]

        # 6. Fetch goals and verify totals, percentages, and breakdowns
        # Fetch as User A
        get_res_a = await client.get("/api/finance/goals", headers=headers_a)
        assert get_res_a.status_code == 200
        goals_a = get_res_a.json()
        assert len(goals_a) == 1
        goal_a = goals_a[0]
        
        assert goal_a["total_manual_saved"] == 8000.0
        assert goal_a["total_saved"] == 8000.0
        assert goal_a["progress_percent"] == 8.0  # 8000 / 100000
        
        # Verify partner split from User A's perspective
        # User A's breakdown should map: "You" -> 5000.0, Partner Name ("Sam User") -> 3000.0
        assert goal_a["partner_breakdown"]["You"] == 5000.0
        assert goal_a["partner_breakdown"]["Sam User"] == 3000.0

        # Fetch as User B
        get_res_b = await client.get("/api/finance/goals", headers=headers_b)
        goals_b = get_res_b.json()
        goal_b = goals_b[0]
        
        # Verify partner split from User B's perspective
        # User B's breakdown should map: "You" -> 3000.0, Partner Name ("Alex User") -> 5000.0
        assert goal_b["partner_breakdown"]["You"] == 3000.0
        assert goal_b["partner_breakdown"]["Alex User"] == 5000.0

        # 7. Test linking a manual asset
        # Let's create a manual cash asset for User A
        asset_payload = {
            "asset_type": "Cash",
            "value": 12000.0,
            "description": "HYSA Shared Cash"
        }
        asset_res = await client.post("/api/finance/manual-assets", json=asset_payload, headers=headers_a)
        assert asset_res.status_code == 200
        asset_id = asset_res.json()["id"]

        # User A creates a goal linked to this manual asset
        goal_linked_payload = {
            "title": "Emergency Fund",
            "category": "Emergency Fund",
            "target_amount": 20000.0,
            "target_date": target_date,
            "linked_asset_type": "manual_asset",
            "linked_asset_id": asset_id
        }
        create_linked_res = await client.post("/api/finance/goals", json=goal_linked_payload, headers=headers_a)
        assert create_linked_res.status_code == 200
        linked_goal_id = create_linked_res.json()["id"]

        # Fetch goals and verify the linked asset value is computed in total_saved
        get_res_linked = await client.get("/api/finance/goals", headers=headers_a)
        goals_list = get_res_linked.json()
        
        emerg_goal = next(g for g in goals_list if g["id"] == linked_goal_id)
        assert emerg_goal["linked_asset_value"] == 12000.0
        assert emerg_goal["total_saved"] == 12000.0  # No contributions yet, just linked asset value
        assert emerg_goal["progress_percent"] == 60.0 # 12000 / 20000

        # Add manual contribution of $1,000 to the linked goal
        await client.post(
            f"/api/finance/goals/{linked_goal_id}/contributions",
            json={"amount": 1000.0},
            headers=headers_a
        )
        
        # Verify total saved is now manual contribution ($1,000) + linked asset value ($12,000) = $13,000
        get_res_linked2 = await client.get("/api/finance/goals", headers=headers_a)
        emerg_goal2 = next(g for g in get_res_linked2.json() if g["id"] == linked_goal_id)
        assert emerg_goal2["total_manual_saved"] == 1000.0
        assert emerg_goal2["linked_asset_value"] == 12000.0
        assert emerg_goal2["total_saved"] == 13000.0
        assert emerg_goal2["progress_percent"] == 65.0

        # 8. Test deletion of a contribution
        del_contrib_res = await client.delete(
            f"/api/finance/goals/{goal_id}/contributions/{contrib_b_id}",
            headers=headers_b
        )
        assert del_contrib_res.status_code == 200
        
        # Verify the total saved decreased
        get_res_after_del = await client.get("/api/finance/goals", headers=headers_a)
        house_goal_after_del = next(g for g in get_res_after_del.json() if g["id"] == goal_id)
        assert house_goal_after_del["total_manual_saved"] == 5000.0  # Sam's $3000 is deleted

        # 8b. Test editing / patching the goal (including income_sources and cash_flows)
        patch_payload = {
            "title": "Buy a Mansion",
            "income_sources": "Salary, Side Hustle",
            "cash_flows": '[{"id":"1","owner":"You","type":"continuous","amount":600.0,"label":"Salary Update"}]'
        }
        patch_res = await client.patch(f"/api/finance/goals/{goal_id}", json=patch_payload, headers=headers_a)
        assert patch_res.status_code == 200
        patched_data = patch_res.json()
        assert patched_data["title"] == "Buy a Mansion"
        assert patched_data["income_sources"] == "Salary, Side Hustle"
        assert patched_data["cash_flows"] == '[{"id":"1","owner":"You","type":"continuous","amount":600.0,"label":"Salary Update"}]'
        
        # Verify in fetched list
        get_res_patched = await client.get("/api/finance/goals", headers=headers_a)
        mansion_goal = next(g for g in get_res_patched.json() if g["id"] == goal_id)
        assert mansion_goal["title"] == "Buy a Mansion"
        assert mansion_goal["income_sources"] == "Salary, Side Hustle"
        assert mansion_goal["cash_flows"] == '[{"id":"1","owner":"You","type":"continuous","amount":600.0,"label":"Salary Update"}]'

        # 9. Test deletion of a goal
        del_goal_res = await client.delete(f"/api/finance/goals/{goal_id}", headers=headers_b)
        assert del_goal_res.status_code == 200
        
        # Verify the goal is deleted
        get_res_final = await client.get("/api/finance/goals", headers=headers_a)
        assert len([g for g in get_res_final.json() if g["id"] == goal_id]) == 0
