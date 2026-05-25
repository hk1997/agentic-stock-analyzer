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
