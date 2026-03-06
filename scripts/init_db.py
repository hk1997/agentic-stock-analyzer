import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.models import Base
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "local.env"))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/stock_analyzer")

async def init_db():
    print(f"Initializing database at {DATABASE_URL}...")
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        # Create standard tables within one transaction
        await conn.run_sync(Base.metadata.create_all)
        
    # Convert TimescaleDB hypertables in separate transactions
    async with engine.begin() as conn:
        try:
             await conn.execute(text("SELECT create_hypertable('stock_daily_prices', 'time', if_not_exists => TRUE, migrate_data => TRUE);"))
             print("Created hypertable: stock_daily_prices")
        except Exception as e:
             print(f"Hypertable daily exists or error: {e}")
             
    async with engine.begin() as conn:
        try:
             await conn.execute(text("SELECT create_hypertable('stock_weekly_prices', 'time', if_not_exists => TRUE, migrate_data => TRUE);"))
             print("Created hypertable: stock_weekly_prices")
        except Exception as e:
             print(f"Hypertable weekly exists or error: {e}")

    await engine.dispose()
    print("Database initialization complete.")

if __name__ == "__main__":
    asyncio.run(init_db())
