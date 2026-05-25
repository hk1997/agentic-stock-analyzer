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
        "email": f"test_upload_{run_id}@example.com",
        "password": "SecurePassword123!",
        "name": "Test Upload User"
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
async def test_robust_csv_parsing(unique_user_credentials):
    """
    Test uploading a CSV with different header casings, spaces, currency symbols, and commas.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await get_auth_headers(client, unique_user_credentials)
        
        # CSV content with lowercase/mixed-case headers, spaces, commas, and currency symbols
        csv_content = (
            "  date  ,  category  ,  amount  ,  description  ,  joint  \n"
            "2023-10-10,Groceries,\"$1,250.50\",UBER TRIP ABCDE,false\n"
            "10/11/2023,Dining,£45.00,Tesco Store,yes\n"
            "2023-10-12T15:30:00Z,Utilities,€120.10,Electric Bill,1\n"
        )
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        upload_res = await client.post(
            "/api/finance/expenses/upload",
            files={"file": ("test_robust.csv", csv_file, "text/csv")},
            headers=headers
        )
        
        assert upload_res.status_code == 200
        data = upload_res.json()
        assert data["status"] == "success"
        assert data["added"] == 3
        
        # Verify the details of the uploaded expenses
        expenses_res = await client.get("/api/finance/expenses", headers=headers)
        assert expenses_res.status_code == 200
        expenses = expenses_res.json()
        assert len(expenses) == 3
        
        # Verify currency and comma parsing
        uber_exp = next(e for e in expenses if "UBER" in e["description"])
        assert uber_exp["amount"] == 1250.50
        assert uber_exp["category"] == "Groceries"
        assert uber_exp["is_joint"] == 0
        
        tesco_exp = next(e for e in expenses if "Tesco" in e["description"])
        assert tesco_exp["amount"] == 45.00
        assert tesco_exp["category"] == "Dining"
        assert tesco_exp["is_joint"] == 1
        
        elec_exp = next(e for e in expenses if "Electric" in e["description"])
        assert elec_exp["amount"] == 120.10
        assert elec_exp["category"] == "Utilities"
        assert elec_exp["is_joint"] == 1

@pytest.mark.anyio
async def test_upload_transaction_safety(unique_user_credentials):
    """
    Test that an invalid row in a CSV does not poison the transaction for other valid rows.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await get_auth_headers(client, unique_user_credentials)
        
        # 2nd row has invalid date format
        csv_content = (
            "Date,Category,Amount,Description,IsJoint\n"
            "2023-10-10,Groceries,50.00,Good Row 1,false\n"
            "invalid-date,Groceries,30.00,Bad Row 2,false\n"
            "2023-10-12,Utilities,100.00,Good Row 3,false\n"
        )
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        upload_res = await client.post(
            "/api/finance/expenses/upload",
            files={"file": ("test_safety.csv", csv_file, "text/csv")},
            headers=headers
        )
        
        assert upload_res.status_code == 200
        data = upload_res.json()
        assert data["status"] == "success"
        assert data["added"] == 2  # Row 1 and Row 3 added, Row 2 skipped
        
        expenses_res = await client.get("/api/finance/expenses", headers=headers)
        assert expenses_res.status_code == 200
        expenses = expenses_res.json()
        assert len(expenses) == 2
        descriptions = [e["description"] for e in expenses]
        assert "Good Row 1" in descriptions
        assert "Good Row 3" in descriptions
        assert "Bad Row 2" not in descriptions

@pytest.mark.anyio
async def test_overly_broad_regex_rejected(unique_user_credentials):
    """
    Test that overly broad regex patterns (like .* or .*.*) are rejected when creating a category rule.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await get_auth_headers(client, unique_user_credentials)
        
        # Reject basic .*
        res1 = await client.post("/api/finance/category-rules", json={
            "regex_pattern": ".*",
            "category_name": "Transport"
        }, headers=headers)
        assert res1.status_code == 400
        assert "too broad" in res1.json()["detail"]
        
        # Reject .*.*
        res2 = await client.post("/api/finance/category-rules", json={
            "regex_pattern": ".*.*",
            "category_name": "Transport"
        }, headers=headers)
        assert res2.status_code == 400
        assert "too broad" in res2.json()["detail"]
        
        # Reject just asterisks or dots
        res3 = await client.post("/api/finance/category-rules", json={
            "regex_pattern": "***",
            "category_name": "Transport"
        }, headers=headers)
        # Should raise invalid regex error (re.error from compile) or broad check
        assert res3.status_code == 400
        
        # Accept valid rules
        res_ok = await client.post("/api/finance/category-rules", json={
            "regex_pattern": ".*uber.*",
            "category_name": "Transport"
        }, headers=headers)
        assert res_ok.status_code == 200

@pytest.mark.anyio
async def test_transaction_history_upload(unique_user_credentials):
    """
    Test uploading the real transactionHistory.csv from Downloads folder.
    """
    path = "/Users/hardikkhandelwal/Downloads/transactionHistory.csv"
    if not os.path.exists(path):
        pytest.skip(f"Test file {path} not found")
        
    with open(path, "rb") as f:
        file_content = f.read()
        
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await get_auth_headers(client, unique_user_credentials)
        
        upload_res = await client.post(
            "/api/finance/expenses/upload",
            files={"file": ("transactionHistory.csv", io.BytesIO(file_content), "text/csv")},
            headers=headers
        )
        
        assert upload_res.status_code == 200
        data = upload_res.json()
        assert data["status"] == "success"
        # There are 51 rows total in the CSV.
        # Line 51 is a positive PAYMENT (836.00), which should be skipped.
        # The other 50 rows are negative amounts (expenses), which should be added.
        assert data["added"] == 50
        
        # Verify the database has indeed 50 expenses
        expenses_res = await client.get("/api/finance/expenses", headers=headers)
        assert expenses_res.status_code == 200
        expenses = expenses_res.json()
        assert len(expenses) == 50

@pytest.mark.anyio
async def test_update_expense_category(unique_user_credentials):
    """
    Test that PATCH /api/finance/expenses/{expense_id} successfully updates an expense's category.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await get_auth_headers(client, unique_user_credentials)
        
        # 1. Create a manual expense
        create_res = await client.post("/api/finance/expenses", json={
            "date": "2023-10-01T00:00:00Z",
            "category": "Uncategorized",
            "amount": 10.0,
            "description": "One-time test item",
            "is_joint": False
        }, headers=headers)
        assert create_res.status_code == 200
        expense_id = create_res.json()["id"]
        
        # 2. Update category using PATCH
        patch_res = await client.patch(f"/api/finance/expenses/{expense_id}", json={
            "category": "Gifts"
        }, headers=headers)
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["category"] == "Gifts"
        
        # 3. Retrieve and double-check
        get_res = await client.get("/api/finance/expenses", headers=headers)
        assert get_res.status_code == 200
        expenses = get_res.json()
        assert len(expenses) == 1
        assert expenses[0]["category"] == "Gifts"

@pytest.mark.anyio
async def test_duplicate_upload_prevention(unique_user_credentials):
    """
    Test that uploading the same CSV file twice does not result in duplicate DB entries.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await get_auth_headers(client, unique_user_credentials)
        
        csv_content = (
            "Date,Category,Amount,Description,IsJoint\n"
            "2023-10-10,Groceries,30.00,Unique PRET Coffee,false\n"
            "2023-10-11,Dining,15.50,Unique Starbucks,false\n"
        )
        
        # First upload
        csv_file1 = io.BytesIO(csv_content.encode('utf-8'))
        res1 = await client.post(
            "/api/finance/expenses/upload",
            files={"file": ("test_dup.csv", csv_file1, "text/csv")},
            headers=headers
        )
        assert res1.status_code == 200
        assert res1.json()["added"] == 2
        
        # Second upload of the same content
        csv_file2 = io.BytesIO(csv_content.encode('utf-8'))
        res2 = await client.post(
            "/api/finance/expenses/upload",
            files={"file": ("test_dup.csv", csv_file2, "text/csv")},
            headers=headers
        )
        assert res2.status_code == 200
        assert res2.json()["added"] == 0  # 0 added because they are duplicates!
        
        # Verify the database has only 2 expenses, not 4
        get_res = await client.get("/api/finance/expenses", headers=headers)
        assert get_res.status_code == 200
        assert len(get_res.json()) == 2

@pytest.mark.anyio
async def test_upload_with_defaults(unique_user_credentials):
    """
    Test that uploading with default_category and default_is_joint query parameters works.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await get_auth_headers(client, unique_user_credentials)
        
        csv_content = (
            "Date,Category,Amount,Description,IsJoint\n"
            "2023-10-10,Uncategorized,30.00,Default Test Item,false\n"
        )
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        res = await client.post(
            "/api/finance/expenses/upload?default_category=Pets&default_is_joint=true",
            files={"file": ("test_defaults.csv", csv_file, "text/csv")},
            headers=headers
        )
        assert res.status_code == 200
        assert res.json()["added"] == 1
        
        # Verify
        get_res = await client.get("/api/finance/expenses", headers=headers)
        assert get_res.status_code == 200
        expenses = get_res.json()
        assert len(expenses) == 1
        assert expenses[0]["category"] == "Pets"
        assert expenses[0]["is_joint"] == 1

@pytest.mark.anyio
async def test_upload_period_and_stats(unique_user_credentials):
    """
    Test uploading a CSV with a default period specified, and verify that detailed stats
    (added, duplicates, failed) are returned correctly in the response.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await get_auth_headers(client, unique_user_credentials)
        
        # CSV content:
        # Row 1: Valid date (2023-10-10), should be shifted to period (2026-05)
        # Row 2: Invalid date format, should fallback to 1st of period (2026-05-01)
        # Row 3: Invalid row that causes parser exception (e.g. empty/invalid amount)
        csv_content = (
            "Date,Category,Amount,Description,IsJoint\n"
            "2023-10-10,Groceries,30.00,Starbucks,false\n"
            "invalid-date,Groceries,15.50,Starbucks,false\n"
            "2023-10-12,Groceries,invalid-amount,Starbucks,false\n"
        )
        
        csv_file1 = io.BytesIO(csv_content.encode('utf-8'))
        res1 = await client.post(
            "/api/finance/expenses/upload?default_period=2026-05",
            files={"file": ("test_stats.csv", csv_file1, "text/csv")},
            headers=headers
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "success"
        # Row 1 and Row 2 should succeed (Row 2 falls back to 2026-05-01), Row 3 fails due to invalid amount
        assert data1["added"] == 2
        assert data1["duplicates"] == 0
        assert data1["failed"] == 1
        
        # Verify the dates in the DB are indeed in 2026-05
        get_res = await client.get("/api/finance/expenses", headers=headers)
        assert get_res.status_code == 200
        expenses = get_res.json()
        assert len(expenses) == 2
        for exp in expenses:
            assert exp["date"].startswith("2026-05")

        # Upload the same content again to test duplicate detection
        csv_file2 = io.BytesIO(csv_content.encode('utf-8'))
        res2 = await client.post(
            "/api/finance/expenses/upload?default_period=2026-05",
            files={"file": ("test_stats.csv", csv_file2, "text/csv")},
            headers=headers
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["added"] == 0
        assert data2["duplicates"] == 2
        assert data2["failed"] == 1

@pytest.mark.anyio
async def test_revolut_statement_upload(unique_user_credentials):
    """
    Test uploading the real revolut_acc_statement.csv from Downloads folder.
    """
    path = "/Users/hardikkhandelwal/Downloads/revolut_acc_statement.csv"
    if not os.path.exists(path):
        pytest.skip(f"Test file {path} not found")
        
    with open(path, "rb") as f:
        file_content = f.read()
        
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await get_auth_headers(client, unique_user_credentials)
        
        upload_res = await client.post(
            "/api/finance/expenses/upload",
            files={"file": ("revolut_acc_statement.csv", io.BytesIO(file_content), "text/csv")},
            headers=headers
        )
        
        assert upload_res.status_code == 200
        data = upload_res.json()
        assert data["status"] == "success"
        
        assert data["added"] > 0
        
        expenses_res = await client.get("/api/finance/expenses", headers=headers)
        assert expenses_res.status_code == 200
        expenses = expenses_res.json()
        assert len(expenses) == data["added"]
        
        # Verify that we imported both positive expenses (stored as amount > 0) and credit/refunds (stored as amount < 0)
        has_positive = False
        has_negative = False
        for exp in expenses:
            if exp["amount"] > 0:
                has_positive = True
            elif exp["amount"] < 0:
                has_negative = True
                assert exp["category"] == "Uncategorized"
        
        assert has_positive, "Should have regular expenses"
        assert has_negative, "Should have credit transactions as negative"

@pytest.mark.anyio
async def test_refund_and_discard_flow(unique_user_credentials):
    """
    Test uploading a CSV with credit transactions, verifying they are negative and uncategorized,
    and testing the deletion/exclude flow.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await get_auth_headers(client, unique_user_credentials)
        
        # CSV content with negative and positive amounts (debits & credits)
        csv_content = (
            "Date,Category,Amount,Description,IsJoint\n"
            "2023-10-10,Groceries,-30.00,Starbucks debit,false\n"
            "2023-10-11,Dining,15.50,Refund from Cafe,false\n"
        )
        
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        upload_res = await client.post(
            "/api/finance/expenses/upload",
            files={"file": ("test_refund.csv", csv_file, "text/csv")},
            headers=headers
        )
        
        assert upload_res.status_code == 200
        data = upload_res.json()
        assert data["status"] == "success"
        # Both rows should be added (one expense, one negative refund)
        assert data["added"] == 2
        assert data["uncategorized"] == 1  # Refund row must be uncategorized
        
        # Verify the database entries
        expenses_res = await client.get("/api/finance/expenses", headers=headers)
        assert expenses_res.status_code == 200
        expenses = expenses_res.json()
        assert len(expenses) == 2
        
        debit_item = next(e for e in expenses if "Starbucks" in e["description"])
        refund_item = next(e for e in expenses if "Refund" in e["description"])
        
        assert debit_item["amount"] == 30.00  # Expense: positive
        assert refund_item["amount"] == -15.50  # Refund: negative
        assert refund_item["category"] == "Uncategorized"  # Bypassed rules/defaults
        
        # Verify that retrieving uncategorized expenses returns the refund item
        uncat_res = await client.get("/api/finance/expenses/uncategorized", headers=headers)
        assert uncat_res.status_code == 200
        uncat_list = uncat_res.json()
        assert len(uncat_list) == 1
        assert uncat_list[0]["id"] == refund_item["id"]
        
        # Exclude/Discard the refund item (DELETE /api/finance/expenses/{id})
        del_res = await client.delete(f"/api/finance/expenses/{refund_item['id']}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "success"
        
        # Verify database now only has 1 expense (the debit Starbucks)
        final_res = await client.get("/api/finance/expenses", headers=headers)
        assert final_res.status_code == 200
        final_expenses = final_res.json()
        assert len(final_expenses) == 1
        assert final_expenses[0]["id"] == debit_item["id"]

@pytest.mark.anyio
async def test_linked_personal_ownership_switch(unique_user_credentials):
    """
    Test switching ownership of an expense to a linked account and back.
    """
    from app.database import engine
    from app.models import User, LinkedAccount, Expense
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select

    # 1. Register and login User 1
    credentials1 = unique_user_credentials
    credentials2 = {
        "email": f"partner_{credentials1['email']}",
        "password": "SecurePassword123!",
        "name": "Partner User"
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers1 = await get_auth_headers(client, credentials1)
        headers2 = await get_auth_headers(client, credentials2)

        # 2. Get user IDs from database
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as db:
            user1_res = await db.execute(select(User).where(User.email == credentials1["email"]))
            user1 = user1_res.scalar_one()
            
            user2_res = await db.execute(select(User).where(User.email == credentials2["email"]))
            user2 = user2_res.scalar_one()

            # Create a link from User 1 to User 2 (and vice versa)
            link1 = LinkedAccount(user_id=user1.id, linked_user_id=user2.id)
            link2 = LinkedAccount(user_id=user2.id, linked_user_id=user1.id)
            db.add_all([link1, link2])
            await db.commit()

        # 3. Create an expense owned by User 1
        create_res = await client.post("/api/finance/expenses", json={
            "date": "2023-10-01T00:00:00Z",
            "category": "Groceries",
            "amount": 50.0,
            "description": "User 1 personal coffee",
            "is_joint": False
        }, headers=headers1)
        assert create_res.status_code == 200
        res_json = create_res.json()
        expense_id = res_json["id"]
        assert res_json["payer_id"] == user1.id

        # 4. Patch expense to be linked-personal (owned by User 2)
        patch_res = await client.patch(f"/api/finance/expenses/{expense_id}", json={
            "ownership_type": "linked-personal"
        }, headers=headers1)
        assert patch_res.status_code == 200
        patched = patch_res.json()
        assert patched["is_joint"] == 0
        assert patched["owner_id"] == user2.id
        assert patched["payer_id"] == user1.id

        # 5. User 1 can still edit it (because they are linked) and change it back to my-personal
        patch_back_res = await client.patch(f"/api/finance/expenses/{expense_id}", json={
            "ownership_type": "my-personal"
        }, headers=headers1)
        assert patch_back_res.status_code == 200
        patched_back = patch_back_res.json()
        assert patched_back["is_joint"] == 0
        assert patched_back["owner_id"] == user1.id
        assert patched_back["payer_id"] == user1.id
