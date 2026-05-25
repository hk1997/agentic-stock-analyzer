import uuid
import pytest
from httpx import ASGITransport, AsyncClient
import sys
import os
import io

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
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

@pytest.fixture
def unique_user_credentials():
    run_id = str(uuid.uuid4())[:8]
    return {
        "email": f"test_cat_{run_id}@example.com",
        "password": "SecurePassword123!",
        "name": "Test Cat User"
    }

async def get_auth_headers(client: AsyncClient, credentials: dict) -> dict:
    # Register user
    reg_res = await client.post("/api/auth/register", json=credentials)
    assert reg_res.status_code == 200
    
    # Login user
    log_res = await client.post("/api/auth/login", data={
        "username": credentials["email"],
        "password": credentials["password"]
    })
    assert log_res.status_code == 200
    token = log_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.anyio
async def test_category_rules_lifecycle(unique_user_credentials):
    """
    Test creating rules, retroactive categorization, fetching uncategorized,
    matching rules on CSV uploads, and month-based filtering.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await get_auth_headers(client, unique_user_credentials)
        
        # 1. Add some initial uncategorized and categorized expenses manually
        # Expense 1: Uncategorized Uber
        exp1_res = await client.post("/api/finance/expenses", json={
            "date": "2023-10-05T12:00:00Z",
            "category": "Uncategorized",
            "amount": 25.50,
            "description": "UBER TRIP 12345",
            "is_joint": False
        }, headers=headers)
        assert exp1_res.status_code == 200
        
        # Expense 2: Uncategorized Lyft
        exp2_res = await client.post("/api/finance/expenses", json={
            "date": "2023-10-06T15:00:00Z",
            "category": "Uncategorized",
            "amount": 18.20,
            "description": "LYFT RIDE 9876",
            "is_joint": False
        }, headers=headers)
        assert exp2_res.status_code == 200
        
        # Expense 3: Already categorized Food
        exp3_res = await client.post("/api/finance/expenses", json={
            "date": "2023-11-01T08:00:00Z",
            "category": "Food",
            "amount": 12.00,
            "description": "Starbucks Coffee",
            "is_joint": False
        }, headers=headers)
        assert exp3_res.status_code == 200

        # 2. Get uncategorized expenses and verify we have exactly 2
        uncat_res = await client.get("/api/finance/expenses/uncategorized", headers=headers)
        assert uncat_res.status_code == 200
        uncat_data = uncat_res.json()
        assert len(uncat_data) == 2
        descriptions = [e["description"] for e in uncat_data]
        assert "UBER TRIP 12345" in descriptions
        assert "LYFT RIDE 9876" in descriptions

        # 3. Create a rule for Uber and verify retroactive application
        rule_res = await client.post("/api/finance/category-rules", json={
            "regex_pattern": ".*uber.*",
            "category_name": "Transport"
        }, headers=headers)
        assert rule_res.status_code == 200
        rule_data = rule_res.json()
        assert rule_data["status"] == "success"
        assert rule_data["updated_expenses"] == 1  # retroactively updated Uber

        # 4. Get uncategorized expenses again, verify only Lyft remains
        uncat_res2 = await client.get("/api/finance/expenses/uncategorized", headers=headers)
        assert uncat_res2.status_code == 200
        uncat_data2 = uncat_res2.json()
        assert len(uncat_data2) == 1
        assert uncat_data2[0]["description"] == "LYFT RIDE 9876"

        # Verify that the Uber expense was indeed updated to "Transport"
        expenses_res = await client.get("/api/finance/expenses", headers=headers)
        assert expenses_res.status_code == 200
        all_expenses = expenses_res.json()
        uber_exp = next(e for e in all_expenses if "UBER" in e["description"])
        assert uber_exp["category"] == "Transport"

        # 5. Create an invalid regex pattern rule and verify error response
        invalid_rule_res = await client.post("/api/finance/category-rules", json={
            "regex_pattern": "[invalid-regex*",
            "category_name": "Error"
        }, headers=headers)
        assert invalid_rule_res.status_code == 400

        # 6. Test CSV upload auto-categorization matching rules
        # Let's upload a CSV containing:
        # - One row matching Uber (should auto-categorize to "Transport")
        # - One row matching Lyft (should remain "Uncategorized" since no rule exists yet)
        # - One row with a preset category (should use preset category or default to Uncategorized if it was Uncategorized)
        csv_content = (
            "Date,Category,Amount,Description,IsJoint\n"
            "2023-10-10,Uncategorized,30.00,UBER TRIP ABCDE,false\n"
            "2023-10-11,Uncategorized,15.50,LYFT RIDE ABC,false\n"
            "2023-10-12,Groceries,45.00,Tesco Store,false\n"
        )
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        upload_res = await client.post(
            "/api/finance/expenses/upload",
            files={"file": ("test_expenses.csv", csv_file, "text/csv")},
            headers=headers
        )
        assert upload_res.status_code == 200
        upload_data = upload_res.json()
        assert upload_data["status"] == "success"
        assert upload_data["added"] == 3
        # Uber matches rule -> Transport (not uncategorized)
        # Lyft -> Uncategorized (uncategorized)
        # Tesco -> Groceries (not uncategorized)
        # So exactly 1 uncategorized expense added
        assert upload_data["uncategorized"] == 1

        # 7. Verify the uploaded expenses categories
        exp_res = await client.get("/api/finance/expenses", headers=headers)
        uploaded = exp_res.json()
        
        uber_uploaded = next(e for e in uploaded if e["description"] == "UBER TRIP ABCDE")
        assert uber_uploaded["category"] == "Transport"
        
        lyft_uploaded = next(e for e in uploaded if e["description"] == "LYFT RIDE ABC")
        assert lyft_uploaded["category"] == "Uncategorized"
        
        tesco_uploaded = next(e for e in uploaded if e["description"] == "Tesco Store")
        assert tesco_uploaded["category"] == "Groceries"

        # 8. Test Month-based filtering
        # Get October 2023 expenses
        oct_res = await client.get("/api/finance/expenses?month=2023-10", headers=headers)
        assert oct_res.status_code == 200
        oct_data = oct_res.json()
        # Should have: Uber Trip 12345, Lyft Ride 9876, UBER TRIP ABCDE, LYFT RIDE ABC, Tesco Store
        assert len(oct_data) == 5
        
        # Get November 2023 expenses
        nov_res = await client.get("/api/finance/expenses?month=2023-11", headers=headers)
        assert nov_res.status_code == 200
        nov_data = nov_res.json()
        # Should have Starbucks Coffee
        assert len(nov_data) == 1
        assert nov_data[0]["description"] == "Starbucks Coffee"

        # Get December 2023 expenses (should be empty)
        dec_res = await client.get("/api/finance/expenses?month=2023-12", headers=headers)
        assert dec_res.status_code == 200
        assert len(dec_res.json()) == 0

        # Send invalid format
        bad_format_res = await client.get("/api/finance/expenses?month=2023-10-05", headers=headers)
        assert bad_format_res.status_code == 400
