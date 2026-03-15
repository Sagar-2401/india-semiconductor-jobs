"""India Semiconductor Jobs Platform — FastAPI Backend"""
import os
import sys

# Add parent dir to path so we can import from scraper/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime

try:
    from backend import database as db
except ImportError:
    import database as db

try:
    from backend.resume_analyzer import full_resume_analysis
except ImportError:
    from resume_analyzer import full_resume_analysis

import asyncio
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

# Track last refresh time globally
_last_refresh = {"time": None, "jobs_added": 0}


def run_scraper_task():
    try:
        from scraper.job_scraper import main as run_scraper
        print("[CRON] Running scheduled scraper job...")
        run_scraper()
        _last_refresh["time"] = datetime.utcnow().isoformat() + "Z"
        print(f"[CRON] Refresh complete at {_last_refresh['time']}")
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

    # Set up background scheduler — refresh every 30 minutes
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_scraper_task, 'interval', minutes=30, id='scraper_job')
    scheduler.start()

    # Run the scraper immediately on first boot
    _last_refresh["time"] = datetime.utcnow().isoformat() + "Z"
    asyncio.get_event_loop().run_in_executor(None, run_scraper_task)

    yield

    # Shutdown tasks
    scheduler.shutdown()


app = FastAPI(title="India Semiconductor Jobs API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── STATIC FRONTEND ────────────────────────────────────────────────────────

@app.get("/")
def serve_frontend():
    index = os.path.join(ROOT, "frontend", "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "India Semiconductor Jobs API", "docs": "/docs"}


# ─── JOB DATA APIs ──────────────────────────────────────────────────────────

@app.get("/api/stats")
def stats():
    s = db.get_stats()
    s["last_refresh"] = _last_refresh.get("time")
    return s


@app.get("/api/refresh-status")
def refresh_status():
    return {
        "last_refresh": _last_refresh.get("time"),
        "refresh_interval_minutes": 30,
    }


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


# ─── RESUME ANALYZER APIs ───────────────────────────────────────────────────

@app.post("/api/resume/analyze")
async def analyze_resume(
    file: UploadFile = File(..., description="PDF resume file"),
    role: str = Form("VLSI", description="Target role: VLSI, FPGA, Verification, etc."),
    company: str = Form("", description="Target company: Intel, AMD, NVIDIA, etc. (empty = all)"),
):
    """Upload a PDF resume and get ATS score + role-specific feedback + company bypass analysis."""
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF files are supported. Please upload a .pdf file."}

    # Read file in memory (no disk storage for privacy)
    try:
        pdf_bytes = await file.read()
    except Exception as e:
        return {"error": f"Could not read file: {e}"}

    if len(pdf_bytes) > 10 * 1024 * 1024:  # 10MB limit
        return {"error": "File too large. Maximum size is 10MB."}

    if len(pdf_bytes) < 100:
        return {"error": "File appears to be empty or corrupted."}

    # Run analysis
    try:
        result = full_resume_analysis(pdf_bytes, role, company if company else None)
        result["filename"] = file.filename
        return result
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Analysis failed: {e}"}


@app.get("/api/resume/roles")
def get_available_roles():
    """Get list of available target roles for resume analysis."""
    from backend.resume_analyzer import DOMAIN_KEYWORDS
    return {
        "roles": list(DOMAIN_KEYWORDS.keys()),
        "default": "VLSI",
    }


@app.get("/api/resume/companies")
def get_available_companies():
    """Get list of company ATS profiles available for bypass analysis."""
    from backend.resume_analyzer import COMPANY_ATS_PROFILES
    return {
        "companies": [
            {"name": name, "ats_system": p["ats_system"]}
            for name, p in COMPANY_ATS_PROFILES.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  India Semiconductor Jobs Platform v2.0")
    print("  API docs: http://localhost:8000/docs")
    print("  Frontend: http://localhost:8000/")
    print("  Resume analyzer: POST /api/resume/analyze")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
