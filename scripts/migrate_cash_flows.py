import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "local.env"))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/stock_analyzer")

async def migrate():
    print(f"Migrating database at {DATABASE_URL}...")
    engine = create_async_engine(DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE financial_goals ADD COLUMN IF NOT EXISTS cash_flows TEXT;"))
            print("Successfully added cash_flows column to financial_goals table.")
        except Exception as e:
            print(f"Error during migration: {e}")
    await engine.dispose()
    print("Database migration complete.")

if __name__ == "__main__":
    asyncio.run(migrate())
