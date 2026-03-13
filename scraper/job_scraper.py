"""Semiconductor Job Scraper — collects jobs from APIs and career pages."""
import os
import sys
import json
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from backend.database import init_db, insert_job, get_db
from scraper.classifier import classify_job

# Semiconductor search queries
SEARCH_QUERIES = [
    "VLSI design engineer India",
    "RTL design engineer India",
    "physical design engineer India",
    "FPGA engineer India",
    "embedded systems engineer India",
    "semiconductor engineer India",
    "chip design engineer India",
    "verification engineer India",
    "analog design engineer India",
    "hardware design engineer India",
    "SoC architect India",
    "DFT engineer India",
    "STA engineer India fresher",
    "ASIC design India",
]

KNOWN_COMPANIES = [
    "Intel", "AMD", "NVIDIA", "Qualcomm", "Texas Instruments", "Broadcom",
    "Marvell", "Samsung", "NXP", "STMicroelectronics", "Infineon", "Micron",
    "Arm", "Renesas", "Microchip", "MediaTek", "Synopsys", "Cadence",
    "Siemens EDA", "Cisco", "IBM", "Western Digital", "Analog Devices",
    "Tata Elxsi", "Wipro", "HCL", "TCS", "Tessolve", "KPIT", "Bosch",
    "L&T Technology", "Sasken", "eInfochips", "Cyient", "Mirafra",
]


def scrape_jsearch(query, num_pages=1):
    """Scrape jobs from JSearch API (RapidAPI). Free: 200 req/month."""
    api_key = os.environ.get("JSEARCH_API_KEY")
    if not api_key:
        print("[JSearch] No API key set. Skipping.")
        return []
    jobs = []
    url = "https://jsearch.p.rapidapi.com/search"
    headers = {"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
    for page in range(1, num_pages + 1):
        params = {"query": query, "page": str(page), "num_pages": "1",
                  "country": "in", "date_posted": "month"}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code != 200:
                print(f"[JSearch] Error {resp.status_code}: {resp.text[:200]}")
                break
            data = resp.json().get("data", [])
            for item in data:
                jobs.append({
                    "company_name": item.get("employer_name", "Unknown"),
                    "title": item.get("job_title", ""),
                    "location": item.get("job_city", "") or item.get("job_country", "India"),
                    "url": item.get("job_apply_link") or item.get("job_google_link", ""),
                    "source": "jsearch",
                    "description": (item.get("job_description") or "")[:2000],
                    "posted_date": (item.get("job_posted_at_datetime_utc") or "")[:10],
                })
            print(f"[JSearch] '{query}' page {page}: {len(data)} jobs")
            time.sleep(1)
        except Exception as e:
            print(f"[JSearch] Error: {e}")
            break
    return jobs


def scrape_adzuna(query):
    """Scrape jobs from Adzuna API. Free: 500 req/month."""
    app_id = os.environ.get("ADZUNA_APP_ID")
    api_key = os.environ.get("ADZUNA_API_KEY")
    if not app_id or not api_key:
        print("[Adzuna] No API keys set. Skipping.")
        return []
    jobs = []
    url = f"https://api.adzuna.com/v1/api/jobs/in/search/1"
    params = {"app_id": app_id, "app_key": api_key, "what": query,
              "results_per_page": 20, "content-type": "application/json"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"[Adzuna] Error {resp.status_code}")
            return jobs
        data = resp.json().get("results", [])
        for item in data:
            jobs.append({
                "company_name": item.get("company", {}).get("display_name", "Unknown"),
                "title": item.get("title", ""),
                "location": item.get("location", {}).get("display_name", "India"),
                "url": item.get("redirect_url", ""),
                "source": "adzuna",
                "description": (item.get("description") or "")[:2000],
                "posted_date": (item.get("created") or "")[:10],
                "salary_min": int(item.get("salary_min", 0) / 100000) if item.get("salary_min") else None,
                "salary_max": int(item.get("salary_max", 0) / 100000) if item.get("salary_max") else None,
            })
        print(f"[Adzuna] '{query}': {len(data)} jobs")
    except Exception as e:
        print(f"[Adzuna] Error: {e}")
    return jobs


def generate_sample_jobs():
    """Generate realistic sample jobs for demo/testing when no API keys are set."""
    samples = [
        {"company_name": "Intel India", "title": "VLSI Design Engineer - RTL",
         "location": "Bangalore", "description": "RTL design using Verilog/SystemVerilog. Synthesis, timing closure. 0-2 years experience. Knowledge of ASIC design flow required.",
         "salary_min": 18, "salary_max": 30, "source": "demo"},
        {"company_name": "AMD", "title": "Physical Design Engineer",
         "location": "Hyderabad", "description": "Physical design including floorplanning, placement, CTS, routing. Innovus/ICC2 experience. Fresh graduates welcome.",
         "salary_min": 18, "salary_max": 28, "source": "demo"},
        {"company_name": "Qualcomm India", "title": "SoC Verification Engineer",
         "location": "Bangalore", "description": "UVM-based verification of mobile SoC. SystemVerilog, formal verification, coverage analysis. 0-1 year experience.",
         "salary_min": 20, "salary_max": 30, "source": "demo"},
        {"company_name": "Synopsys India", "title": "ASIC DFT Engineer - Fresher",
         "location": "Bangalore", "description": "DFT insertion, scan chain, ATPG, BIST implementation. Tessent/DFTCompiler. Fresh graduate or 0-1 year.",
         "salary_min": 15, "salary_max": 25, "source": "demo"},
        {"company_name": "Cadence Design", "title": "STA Engineer",
         "location": "Noida", "description": "Static timing analysis, timing closure, SDC constraints. PrimeTime/Tempus. Entry-level position.",
         "salary_min": 15, "salary_max": 25, "source": "demo"},
        {"company_name": "NVIDIA India", "title": "GPU Architecture Engineer",
         "location": "Bangalore", "description": "GPU architecture, CUDA cores, memory hierarchy. AI accelerator design. MS/PhD preferred. 0-3 years.",
         "salary_min": 25, "salary_max": 45, "source": "demo"},
        {"company_name": "Texas Instruments", "title": "Analog IC Design Engineer",
         "location": "Bangalore", "description": "Analog circuit design: PLL, ADC, DAC, LDO. Cadence Virtuoso. Fresh graduates welcome.",
         "salary_min": 14, "salary_max": 22, "source": "demo"},
        {"company_name": "Broadcom India", "title": "ASIC Design Engineer - Networking",
         "location": "Hyderabad", "description": "ASIC design for ethernet switches. RTL coding, synthesis, netlist verification. 0-2 years exp.",
         "salary_min": 18, "salary_max": 30, "source": "demo"},
        {"company_name": "Tata Elxsi", "title": "FPGA Design Engineer",
         "location": "Bangalore", "description": "FPGA design, Vivado, Vitis HLS. Digital signal processing. Fresher/1-year experience.",
         "salary_min": 6, "salary_max": 12, "source": "demo"},
        {"company_name": "Wipro VLSI", "title": "VLSI Verification Engineer - UVM",
         "location": "Hyderabad", "description": "UVM testbench development, coverage-driven verification. SystemVerilog. Campus hiring.",
         "salary_min": 6, "salary_max": 10, "source": "demo"},
        {"company_name": "Tessolve Semi", "title": "Post-Silicon Validation Engineer",
         "location": "Bangalore", "description": "Post-silicon debug, ATE testing, characterization. Lab equipment. 0-1 year.",
         "salary_min": 8, "salary_max": 15, "source": "demo"},
        {"company_name": "HCL Technologies", "title": "RTL Design Engineer - 5nm",
         "location": "Chennai", "description": "RTL design at 5nm node. Verilog, synthesis, CDC, lint. DFT awareness. Freshers accepted.",
         "salary_min": 8, "salary_max": 14, "source": "demo"},
        {"company_name": "Microchip Technology", "title": "Embedded Firmware Engineer",
         "location": "Chennai", "description": "Firmware for PIC/SAM microcontrollers. C, RTOS, peripheral drivers. 0-2 years experience.",
         "salary_min": 8, "salary_max": 16, "source": "demo"},
        {"company_name": "Bosch India", "title": "Automotive Embedded Engineer",
         "location": "Bangalore", "description": "AUTOSAR, CAN, LIN protocols. Embedded C for automotive ECUs. Fresh graduates welcome.",
         "salary_min": 10, "salary_max": 18, "source": "demo"},
        {"company_name": "KPIT Technologies", "title": "ADAS Hardware Engineer",
         "location": "Pune", "description": "Hardware design for ADAS systems. PCB design, signal integrity, power. 0-1 year exp.",
         "salary_min": 8, "salary_max": 14, "source": "demo"},
        {"company_name": "Marvell Technology", "title": "SoC Design Engineer - 5G",
         "location": "Hyderabad", "description": "5G modem SoC design. RTL, micro-architecture, performance modeling. 0-2 years.",
         "salary_min": 18, "salary_max": 28, "source": "demo"},
        {"company_name": "Samsung Semi India", "title": "Memory Design Engineer",
         "location": "Bangalore", "description": "SRAM/DRAM memory circuit design. Custom layout, characterization. 0-1 year.",
         "salary_min": 15, "salary_max": 25, "source": "demo"},
        {"company_name": "Arm India", "title": "CPU Design Engineer - RISC-V",
         "location": "Bangalore", "description": "CPU pipeline design, cache architecture, branch prediction. RISC-V or ARM ISA. Fresh PhD/MS.",
         "salary_min": 22, "salary_max": 35, "source": "demo"},
        {"company_name": "NXP Semiconductors", "title": "IoT Security Hardware Engineer",
         "location": "Noida", "description": "Secure element design for IoT. Hardware security modules, crypto accelerators. 0-2 yr exp.",
         "salary_min": 12, "salary_max": 20, "source": "demo"},
        {"company_name": "Renesas Electronics", "title": "MCU Application Engineer",
         "location": "Bangalore", "description": "MCU application support. RL78, RX, RA family. Customer design-in. Fresh graduates.",
         "salary_min": 10, "salary_max": 18, "source": "demo"},
    ]
    for s in samples:
        s["posted_date"] = datetime.now().strftime("%Y-%m-%d")
        s.setdefault("url", f"https://example.com/job/{s['company_name'].lower().replace(' ','-')}-{hash(s['title'])%9999}")
    return samples


def process_jobs(raw_jobs):
    """Classify each job and insert into database."""
    inserted = 0
    for job in raw_jobs:
        # Classify
        result = classify_job(job.get("title", ""), job.get("description", ""))
        job["domain"] = result["domain"]
        job["skills"] = ",".join(result["skills"][:8])
        job["fresher_suitable"] = 1 if result["fresher_suitable"] else 0
        if not job.get("salary_min"):
            job["salary_min"] = result.get("salary_estimate_min")
        if not job.get("salary_max"):
            job["salary_max"] = result.get("salary_estimate_max")
        job["experience_min"] = result.get("experience_min", 0)
        job["ai_classified"] = 0
        # Insert
        if insert_job(job):
            inserted += 1
    return inserted


def main():
    print("=" * 60)
    print("  Semiconductor Job Scraper")
    print(f"  Time: {datetime.now().isoformat()}")
    print("=" * 60)
    init_db()
    all_jobs = []
    has_api_keys = bool(os.environ.get("JSEARCH_API_KEY") or os.environ.get("ADZUNA_APP_ID"))

    if has_api_keys:
        # Use a subset of queries to stay within free tier limits
        queries_to_use = SEARCH_QUERIES[:5]
        for query in queries_to_use:
            all_jobs.extend(scrape_jsearch(query))
            time.sleep(1)
            all_jobs.extend(scrape_adzuna(query))
            time.sleep(1)
    else:
        print("[INFO] No API keys found. Loading demo/sample jobs.")
        print("[INFO] Set JSEARCH_API_KEY or ADZUNA_APP_ID in .env for real jobs.")
        all_jobs = generate_sample_jobs()

    print(f"\n[TOTAL] Collected {len(all_jobs)} raw jobs")
    inserted = process_jobs(all_jobs)
    print(f"[DONE] Inserted {inserted} new jobs into database\n")

    # Print stats
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    fresher = conn.execute("SELECT COUNT(*) FROM jobs WHERE fresher_suitable=1").fetchone()[0]
    conn.close()
    print(f"  Total jobs in DB: {total}")
    print(f"  Fresher suitable: {fresher}")


if __name__ == "__main__":
    main()
