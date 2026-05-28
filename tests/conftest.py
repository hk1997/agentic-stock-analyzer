import os
import sys

# Override DATABASE_URL to use a dedicated test database (stock_analyzer_test)
# to prevent tests from dropping and clearing the development database.
db_url = os.environ.get("DATABASE_URL")
if not db_url:
    # Load from env files first if not set in environment
    from dotenv import load_dotenv
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, "local.env"))
    load_dotenv(os.path.join(project_root, ".env"))
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/stock_analyzer")

# Append/replace database name with test suffix
if "/stock_analyzer" in db_url and not db_url.endswith("/stock_analyzer_test"):
    os.environ["DATABASE_URL"] = db_url.replace("/stock_analyzer", "/stock_analyzer_test")

import pytest
from app.database import engine


@pytest.fixture(autouse=True, scope="function")
async def clean_database_connections():
    """
    Autouse fixture to dispose of the async engine's connection pool
    after each test. This prevents cross-loop connection leak issues
    (e.g., RuntimeError: got Future attached to a different loop)
    when running multiple async tests sequentially.
    """
    yield
    await engine.dispose()
    try:
        from app.cache import close_valkey_pool
        await close_valkey_pool()
    except Exception:
        pass

