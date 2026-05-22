import asyncio
import sys
import os
import logging

# Ensure root project dir is on sys.path so app modules resolve
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

if os.path.exists(os.path.join(PROJECT_ROOT, "local.env")):
    load_dotenv(os.path.join(PROJECT_ROOT, "local.env"))
else:
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Configure basic logging for the script
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

from app.email_service import run_daily_job

async def main():
    try:
        await run_daily_job()
    except Exception as e:
        logging.error(f"Failed to run daily email job: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
