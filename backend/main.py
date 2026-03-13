"""India Semiconductor Jobs Platform — FastAPI Backend"""
import os
import sys

# Add parent dir to path so we can import from scraper/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
from dotenv import load_dotenv
try:
    from backend import database as db
except ImportError:
    import database as db

import asyncio
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
import os
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

def run_scraper_task():
    try:
        from scraper.job_scraper import main as run_scraper
        print("[CRON] Running scheduled scraper job...")
        run_scraper()
    except Exception as e:
        print(f"[CRON] Error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    db.init_db()
    
    # Check if companies are seeded
    stats = db.get_stats()
    if stats["companies"] == 0:
        print("[STARTUP] Companies missing. Running seed script...")
        try:
            from scraper.seed_companies import seed_companies
            seed_companies()
        except Exception as e:
            print(f"[STARTUP] Error seeding companies: {e}")

    # Set up background scheduler for jobs every 6 hours
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_scraper_task, 'interval', hours=6)
    scheduler.start()
    
    # Run the scraper immediately on first boot so it's not empty
    # Do this in background thread to not block FastAPI startup
    asyncio.get_event_loop().run_in_executor(None, run_scraper_task)
    
    yield
    
    # Shutdown tasks
    scheduler.shutdown()

app = FastAPI(title="India Semiconductor Jobs API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def serve_frontend():
    index = os.path.join(ROOT, "frontend", "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "India Semiconductor Jobs API", "docs": "/docs"}


@app.get("/api/stats")
def stats():
    return db.get_stats()


@app.get("/api/companies")
def list_companies(
    search: Optional[str] = Query(None, description="Search by name, location, description"),
    domain: Optional[str] = Query(None, description="Filter by domain code (VL, FP, AI, etc.)"),
    fresher_min: Optional[int] = Query(None, ge=1, le=5, description="Minimum fresher score"),
    sort: str = Query("best", description="Sort: best, salary, name"),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    return db.get_companies(search, domain, fresher_min, sort, limit, offset)


@app.get("/api/jobs")
def list_jobs(
    search: Optional[str] = Query(None, description="Search title, company, description"),
    domain: Optional[str] = Query(None, description="Filter by domain: VLSI, FPGA, Embedded, etc."),
    fresher: Optional[bool] = Query(None, description="Show only fresher-suitable jobs"),
    salary_min: Optional[int] = Query(None, description="Minimum salary in LPA"),
    location: Optional[str] = Query(None, description="Filter by location"),
    sort: str = Query("recent", description="Sort: recent, salary, best"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return db.get_jobs(search, domain, fresher, salary_min, location, sort, limit, offset)


@app.get("/api/domains")
def list_domains():
    return db.get_domains()


@app.post("/api/classify")
def classify_job(payload: dict):
    try:
        from scraper.classifier import classify_job as _classify
        result = _classify(payload.get("title", ""), payload.get("description", ""))
        return result
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  India Semiconductor Jobs Platform")
    print("  API docs: http://localhost:8000/docs")
    print("  Frontend: http://localhost:8000/")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
