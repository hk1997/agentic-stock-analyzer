import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), "local.env"))
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/stock_analyzer")

# Route to test database when running tests to protect the dev database
if "pytest" in sys.modules or "unittest" in sys.modules:
    parts = DATABASE_URL.split('/')
    db_name = parts[-1]
    if '?' in db_name:
        name_part, query_part = db_name.split('?', 1)
        if not name_part.endswith('_test'):
            parts[-1] = f"{name_part}_test?{query_part}"
    else:
        if not db_name.endswith('_test'):
            parts[-1] = f"{db_name}_test"
    DATABASE_URL = '/'.join(parts)

# Create Async Engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create session factory
async_session = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)

async def get_db_session() -> AsyncSession: # type: ignore
    """Dependency for FastAPI endpoints to yield a DB session."""
    async with async_session() as session:
        yield session
