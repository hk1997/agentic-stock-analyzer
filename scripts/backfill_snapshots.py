import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
import random

# Ensure root project dir is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.database import async_session
from app.models import User, NetWorthSnapshot
from sqlalchemy import select, delete

async def backfill():
    print("Starting net worth snapshots backfill script...")
    async with async_session() as db:
        # Fetch all users
        res = await db.execute(select(User))
        users = res.scalars().all()
        if not users:
            print("No users found in database. Please register a user first.")
            return

        for u in users:
            print(f"Backfilling snapshots for user: {u.email} (ID: {u.id})")
            
            # Clear existing snapshots to avoid duplicate key errors during backfill
            await db.execute(delete(NetWorthSnapshot).where(NetWorthSnapshot.owner_id == u.id))
            await db.commit()
            
            # Base net worth approximation
            base_assets = 15000.0
            base_liabilities = 3000.0
            
            # We generate monthly snapshots going back 6 months
            now = datetime.now(timezone.utc)
            for months_back in range(6, -1, -1): # From 6 months ago to today
                if months_back == 0:
                    snap_date = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
                else:
                    # Calculate date approximately
                    snap_date = now - timedelta(days=30 * months_back)
                    snap_date = datetime(snap_date.year, snap_date.month, snap_date.day, tzinfo=timezone.utc)

                # Growth factor: net worth grows over time, so backwards it is lower
                factor = 1.0 - (0.04 * months_back) + (random.uniform(-0.02, 0.02))
                factor = max(0.5, factor) # don't go below 50%
                
                assets = base_assets * factor
                liabilities = base_liabilities * (1.1 - (0.02 * months_back))
                liabilities = max(0.0, liabilities)
                
                snapshot = NetWorthSnapshot(
                    owner_id=u.id,
                    date=snap_date,
                    total_assets=round(assets, 2),
                    total_liabilities=round(liabilities, 2)
                )
                db.add(snapshot)
                print(f"  Created snapshot for {snap_date.strftime('%Y-%m-%d')}: Assets=${assets:.2f}, Liabilities=${liabilities:.2f}, Net Worth=${(assets - liabilities):.2f}")
            
            await db.commit()
            print(f"Successfully backfilled snapshots for user {u.email}.\n")

if __name__ == "__main__":
    asyncio.run(backfill())
