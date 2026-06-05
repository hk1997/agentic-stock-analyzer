"""
Agentic Stock Analyzer — FastAPI Backend
Serves the LangGraph agent and financial tracking endpoints.
"""
import os
import sys
import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Ensure root project dir is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if os.path.exists(os.path.join(PROJECT_ROOT, "local.env")):
    load_dotenv(os.path.join(PROJECT_ROOT, "local.env"))
else:
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from app.tasks import update_active_tickers_prices
from app.cache import close_valkey_pool
from app.email_service import run_daily_job

async def take_nightly_net_worth_snapshots():
    from app.database import async_session
    from sqlalchemy import select
    from app.models import User
    from api.routes.finance import capture_user_net_worth_snapshot
    from datetime import datetime, timezone
    
    async with async_session() as db:
        result = await db.execute(select(User.id))
        user_ids = [r[0] for r in result.all()]
        
        now = datetime.now(timezone.utc)
        for user_id in user_ids:
            try:
                await capture_user_net_worth_snapshot(db, user_id, now)
            except Exception as e:
                print(f"Failed to capture snapshot for user {user_id}: {e}")

async def run_monthly_summary_cron_job():
    from app.database import async_session
    from sqlalchemy import select
    from app.models import User
    from app.email_service import run_monthly_summary_job
    
    async with async_session() as db:
        result = await db.execute(select(User.id))
        user_ids = [r[0] for r in result.all()]
        
        for user_id in user_ids:
            try:
                await run_monthly_summary_job(db, user_id)
            except Exception as e:
                print(f"Failed to run monthly summary job for user {user_id}: {e}")

# ── App Setup ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database Tables
    from app.models import Base
    from app.database import engine
    from sqlalchemy import text
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.execute(text("ALTER TABLE portfolios ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE;"))
            except Exception:
                pass # Column might already exist
    except Exception as e:
        print(f"Database initialization failed: {e}")

    # Startup: Kick off lightweight background data refresh for recently active tickers
    asyncio.create_task(update_active_tickers_prices())
    
    # Initialize APScheduler for daily email job
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()
    
    scheduler.add_job(run_daily_job, 'cron', hour=8, minute=0)
    scheduler.add_job(take_nightly_net_worth_snapshots, 'cron', hour=23, minute=59)
    scheduler.add_job(run_monthly_summary_cron_job, 'cron', day=1, hour=9, minute=0)
    scheduler.start()
    
    yield
    
    # Shutdown
    scheduler.shutdown(wait=False)
    await close_valkey_pool()

app = FastAPI(title="Agentic Stock Analyzer API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex="http://.*:5173",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router Registrations ──────────────────────────────────
from api.routes import auth, finance, agent, market, portfolio

app.include_router(auth.router)
app.include_router(finance.router)
app.include_router(agent.router)
app.include_router(market.router)
app.include_router(portfolio.router)

# Static files (vanilla HTML fallback)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ── Routes ─────────────────────────────────────────────────

@app.get("/")
def root():
    """Serve index.html if available, otherwise show API status."""
    from api.routes.agent import agent_graph
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "online", "graph_ready": agent_graph is not None}


@app.get("/api/health")
def health():
    """Health check endpoint for tests and monitoring."""
    from api.routes.agent import agent_graph, _graph_error
    return {
        "status": "healthy",
        "graph_ready": agent_graph is not None,
        "graph_error": _graph_error,
    }


@app.get("/api/dev/init-db")
async def dev_init_db():
    """Temporary route to initialize new tables and run migrations"""
    from app.models import Base
    from app.database import engine
    from sqlalchemy import text
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            try:
                await conn.execute(text("ALTER TABLE portfolios ADD COLUMN owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE;"))
            except Exception:
                pass
        return {"status": "success", "message": "Database initialized and migrated."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
