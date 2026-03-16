"""Semiconductor Job Scraper — collects jobs from APIs and career pages."""
import os
import sys
import re
import time
import requests
from urllib.parse import urljoin
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

# Real company career search URLs — used for sample jobs and URL fallback
COMPANY_CAREER_SITES = {
    "intel": "https://jobs.intel.com/en/search-jobs/India/in",
    "amd": "https://careers.amd.com/careers-home/jobs?loc=India",
    "qualcomm": "https://careers.qualcomm.com/careers/search-jobs?Country=India",
    "synopsys": "https://careers.synopsys.com/job-search-results/?location=India",
    "cadence": "https://cadence.wd1.myworkdayjobs.com/External_Careers",
    "nvidia": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
    "texas instruments": "https://careers.ti.com/search-jobs/India/in",
    "broadcom": "https://broadcom.wd1.myworkdayjobs.com/External_Career",
    "tata elxsi": "https://www.tataelxsi.com/careers",
    "wipro": "https://careers.wipro.com/careers-home/jobs",
    "tessolve": "https://www.tessolve.com/careers/",
    "hcl": "https://www.hcltech.com/careers",
    "microchip": "https://careers.microchip.com/",
    "bosch": "https://careers.smartrecruiters.com/BoschGroup/india",
    "kpit": "https://www.kpit.com/careers/",
    "marvell": "https://marvell.wd1.myworkdayjobs.com/MarvellCareers",
    "samsung": "https://sec.wd3.myworkdayjobs.com/Samsung_Careers",
    "arm": "https://careers.arm.com/search-jobs/India/in",
    "nxp": "https://nxp.wd3.myworkdayjobs.com/careers",
    "renesas": "https://jobs.renesas.com/search/?locationsearch=India",
    "stmicroelectronics": "https://www.st.com/content/st_com/en/about/careers.html",
    "infineon": "https://www.infineon.com/cms/en/careers/",
    "micron": "https://careers.micron.com/careers/search-jobs/India/in",
    "mediatek": "https://careers.mediatek.com/eREC/JobSearch/Detail/India",
    "siemens eda": "https://jobs.siemens.com/careers?q=EDA+India",
}


def strip_html(text):
    """Remove HTML tags from job description text."""
    if not text:
        return text
    return re.sub(r'<[^>]+>', '', text)


def get_career_url(company_name: str, role_hint: str = "") -> str:
    """Return the real career site URL for a given company."""
    base_name = (company_name.lower()
                 .replace(" india", "").replace(" technologies", "")
                 .replace(" semiconductors", "").replace(" semi", "")
                 .replace(" design", "").replace(" technology", "")
                 .replace(" vlsi", "").strip())

    for known_name, url in COMPANY_CAREER_SITES.items():
        if known_name in base_name or base_name in known_name:
            return url

    # Generic Google careers search as last resort
    query = f"{company_name} careers India semiconductor".replace(" ", "+")
    return f"https://www.google.com/search?q={query}"


def is_duplicate(title, company_name):
    """Check if a job with the same title+company already exists (composite key)."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE title=? AND company_name=? LIMIT 1",
            (title, company_name)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


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
                # Prefer specific apply link over generic google link
                apply_url = (item.get("job_apply_link") or
                             item.get("job_google_link") or "")
                # Resolve relative URLs if needed
                if apply_url and apply_url.startswith("/"):
                    apply_url = urljoin("https://jsearch.p.rapidapi.com", apply_url)
                raw_desc = item.get("job_description") or ""
                jobs.append({
                    "company_name": item.get("employer_name", "Unknown"),
                    "title": item.get("job_title", ""),
                    "location": item.get("job_city", "") or item.get("job_country", "India"),
                    "url": apply_url,
                    "source": "jsearch",
                    "description": strip_html(raw_desc[:2000]),
                    "posted_date": (item.get("job_posted_at_datetime_utc") or "")[:10],
                })
            print(f"[JSearch] '{query}' page {page}: {len(data)} jobs")
            time.sleep(1)
        except Exception as e:
            print(f"[JSearch] Error for '{query}': {e}")
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
    url = "https://api.adzuna.com/v1/api/jobs/in/search/1"
    params = {"app_id": app_id, "app_key": api_key, "what": query,
              "results_per_page": 20, "content-type": "application/json"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"[Adzuna] Error {resp.status_code}")
            return jobs
        data = resp.json().get("results", [])
        for item in data:
            # redirect_url is the specific job's apply URL from Adzuna
            apply_url = item.get("redirect_url", "")
            raw_desc = item.get("description") or ""
            jobs.append({
                "company_name": item.get("company", {}).get("display_name", "Unknown"),
                "title": item.get("title", ""),
                "location": item.get("location", {}).get("display_name", "India"),
                "url": apply_url,
                "source": "adzuna",
                "description": strip_html(raw_desc[:2000]),
                "posted_date": (item.get("created") or "")[:10],
                "salary_min": int(item.get("salary_min", 0) / 100000) if item.get("salary_min") else None,
                "salary_max": int(item.get("salary_max", 0) / 100000) if item.get("salary_max") else None,
            })
        print(f"[Adzuna] '{query}': {len(data)} jobs")
    except Exception as e:
        print(f"[Adzuna] Error for '{query}': {e}")
    return jobs


def generate_sample_jobs():
    """Generate realistic sample jobs for demo/testing when no API keys are set.
    Each job uses a real company career search URL — best possible without live scraping.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    samples = [
        {"company_name": "Intel India", "title": "VLSI Design Engineer - RTL",
         "location": "Bangalore",
         "url": "https://jobs.intel.com/en/search-jobs/VLSI/Bangalore/599/1/1/26/3/3/0/0",
         "description": "RTL design using Verilog/SystemVerilog. Synthesis, timing closure. 0-2 years experience. Knowledge of ASIC design flow required.",
         "salary_min": 18, "salary_max": 30, "posted_date": today, "source": "demo"},
        {"company_name": "AMD", "title": "Physical Design Engineer",
         "location": "Hyderabad",
         "url": "https://careers.amd.com/careers-home/jobs?keywords=physical+design&loc=India",
         "description": "Physical design including floorplanning, placement, CTS, routing. Innovus/ICC2 experience. Fresh graduates welcome.",
         "salary_min": 18, "salary_max": 28, "posted_date": today, "source": "demo"},
        {"company_name": "Qualcomm India", "title": "SoC Verification Engineer",
         "location": "Bangalore",
         "url": "https://careers.qualcomm.com/careers/search-jobs?keywords=verification&Country=India",
         "description": "UVM-based verification of mobile SoC. SystemVerilog, formal verification, coverage analysis. 0-1 year experience.",
         "salary_min": 20, "salary_max": 30, "posted_date": today, "source": "demo"},
        {"company_name": "Synopsys India", "title": "ASIC DFT Engineer - Fresher",
         "location": "Bangalore",
         "url": "https://careers.synopsys.com/job-search-results/?keyword=DFT&location=India",
         "description": "DFT insertion, scan chain, ATPG, BIST implementation. Tessent/DFTCompiler. Fresh graduate or 0-1 year.",
         "salary_min": 15, "salary_max": 25, "posted_date": today, "source": "demo"},
        {"company_name": "Cadence Design", "title": "STA Engineer",
         "location": "Noida",
         "url": "https://cadence.wd1.myworkdayjobs.com/External_Careers?q=STA+timing",
         "description": "Static timing analysis, timing closure, SDC constraints. PrimeTime/Tempus. Entry-level position.",
         "salary_min": 15, "salary_max": 25, "posted_date": today, "source": "demo"},
        {"company_name": "NVIDIA India", "title": "GPU Architecture Engineer",
         "location": "Bangalore",
         "url": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?q=GPU+architecture+India",
         "description": "GPU architecture, CUDA cores, memory hierarchy. AI accelerator design. MS/PhD preferred. 0-3 years.",
         "salary_min": 25, "salary_max": 45, "posted_date": today, "source": "demo"},
        {"company_name": "Texas Instruments", "title": "Analog IC Design Engineer",
         "location": "Bangalore",
         "url": "https://careers.ti.com/search-jobs/Analog%20Design/Bangalore/4796/1/1/26/3/3/0/0",
         "description": "Analog circuit design: PLL, ADC, DAC, LDO. Cadence Virtuoso. Fresh graduates welcome.",
         "salary_min": 14, "salary_max": 22, "posted_date": today, "source": "demo"},
        {"company_name": "Broadcom India", "title": "ASIC Design Engineer - Networking",
         "location": "Hyderabad",
         "url": "https://broadcom.wd1.myworkdayjobs.com/External_Career?q=ASIC+design",
         "description": "ASIC design for ethernet switches. RTL coding, synthesis, netlist verification. 0-2 years exp.",
         "salary_min": 18, "salary_max": 30, "posted_date": today, "source": "demo"},
        {"company_name": "Tata Elxsi", "title": "FPGA Design Engineer",
         "location": "Bangalore",
         "url": "https://www.tataelxsi.com/careers#openings",
         "description": "FPGA design, Vivado, Vitis HLS. Digital signal processing. Fresher/1-year experience.",
         "salary_min": 6, "salary_max": 12, "posted_date": today, "source": "demo"},
        {"company_name": "Wipro VLSI", "title": "VLSI Verification Engineer - UVM",
         "location": "Hyderabad",
         "url": "https://careers.wipro.com/careers-home/jobs?q=VLSI+verification",
         "description": "UVM testbench development, coverage-driven verification. SystemVerilog. Campus hiring.",
         "salary_min": 6, "salary_max": 10, "posted_date": today, "source": "demo"},
        {"company_name": "Tessolve Semi", "title": "Post-Silicon Validation Engineer",
         "location": "Bangalore",
         "url": "https://www.tessolve.com/careers/",
         "description": "Post-silicon debug, ATE testing, characterization. Lab equipment. 0-1 year.",
         "salary_min": 8, "salary_max": 15, "posted_date": today, "source": "demo"},
        {"company_name": "HCL Technologies", "title": "RTL Design Engineer - 5nm",
         "location": "Chennai",
         "url": "https://www.hcltech.com/careers/search-jobs?keywords=RTL+design",
         "description": "RTL design at 5nm node. Verilog, synthesis, CDC, lint. DFT awareness. Freshers accepted.",
         "salary_min": 8, "salary_max": 14, "posted_date": today, "source": "demo"},
        {"company_name": "Microchip Technology", "title": "Embedded Firmware Engineer",
         "location": "Chennai",
         "url": "https://careers.microchip.com/job-search-results/?keyword=embedded+firmware&location=India",
         "description": "Firmware for PIC/SAM microcontrollers. C, RTOS, peripheral drivers. 0-2 years experience.",
         "salary_min": 8, "salary_max": 16, "posted_date": today, "source": "demo"},
        {"company_name": "Bosch India", "title": "Automotive Embedded Engineer",
         "location": "Bangalore",
         "url": "https://careers.smartrecruiters.com/BoschGroup/india?search=embedded",
         "description": "AUTOSAR, CAN, LIN protocols. Embedded C for automotive ECUs. Fresh graduates welcome.",
         "salary_min": 10, "salary_max": 18, "posted_date": today, "source": "demo"},
        {"company_name": "KPIT Technologies", "title": "ADAS Hardware Engineer",
         "location": "Pune",
         "url": "https://www.kpit.com/careers/open-positions/?search=hardware",
         "description": "Hardware design for ADAS systems. PCB design, signal integrity, power. 0-1 year exp.",
         "salary_min": 8, "salary_max": 14, "posted_date": today, "source": "demo"},
        {"company_name": "Marvell Technology", "title": "SoC Design Engineer - 5G",
         "location": "Hyderabad",
         "url": "https://marvell.wd1.myworkdayjobs.com/MarvellCareers?q=SoC+design",
         "description": "5G modem SoC design. RTL, micro-architecture, performance modeling. 0-2 years.",
         "salary_min": 18, "salary_max": 28, "posted_date": today, "source": "demo"},
        {"company_name": "Samsung Semi India", "title": "Memory Design Engineer",
         "location": "Bangalore",
         "url": "https://sec.wd3.myworkdayjobs.com/Samsung_Careers?q=memory+design",
         "description": "SRAM/DRAM memory circuit design. Custom layout, characterization. 0-1 year.",
         "salary_min": 15, "salary_max": 25, "posted_date": today, "source": "demo"},
        {"company_name": "Arm India", "title": "CPU Design Engineer - RISC-V",
         "location": "Bangalore",
         "url": "https://careers.arm.com/search-jobs/India/in#%7B%22keyword%22%3A%22CPU%22%7D",
         "description": "CPU pipeline design, cache architecture, branch prediction. RISC-V or ARM ISA. Fresh PhD/MS.",
         "salary_min": 22, "salary_max": 35, "posted_date": today, "source": "demo"},
        {"company_name": "NXP Semiconductors", "title": "IoT Security Hardware Engineer",
         "location": "Noida",
         "url": "https://nxp.wd3.myworkdayjobs.com/careers?q=hardware+security",
         "description": "Secure element design for IoT. Hardware security modules, crypto accelerators. 0-2 yr exp.",
         "salary_min": 12, "salary_max": 20, "posted_date": today, "source": "demo"},
        {"company_name": "Renesas Electronics", "title": "MCU Application Engineer",
         "location": "Bangalore",
         "url": "https://jobs.renesas.com/search/?locationsearch=India&q=MCU",
         "description": "MCU application support. RL78, RX, RA family. Customer design-in. Fresh graduates.",
         "salary_min": 10, "salary_max": 18, "posted_date": today, "source": "demo"},
    ]
    return samples


def process_jobs(raw_jobs):
    """Classify each job, deduplicate, strip HTML, and insert into database."""
    inserted = 0
    skipped = 0
    for job in raw_jobs:
        # Strip HTML from description
        job["description"] = strip_html(job.get("description", ""))

        # Skip duplicates using composite key: title + company_name
        if is_duplicate(job.get("title", ""), job.get("company_name", "")):
            skipped += 1
            continue

        # Ensure URL is a real career link, not an example.com placeholder
        url = job.get("url", "")
        if not url or "example.com" in url:
            job["url"] = get_career_url(job.get("company_name", ""))

        # Resolve relative URLs
        if url and url.startswith("/"):
            job["url"] = urljoin("https://www.linkedin.com", url)

        # Classify job
        try:
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
        except Exception as e:
            print(f"[CLASSIFY] Error classifying '{job.get('title', '')}': {e}")
            continue

        # Insert
        if insert_job(job):
            inserted += 1

    if skipped:
        print(f"[SCRAPER] Skipped {skipped} duplicate jobs")
    return inserted


def main():
    print("=" * 60)
    print("  Semiconductor Job Scraper")
    print(f"  Time: {datetime.now().isoformat()}")
    print("=" * 60)

    # Ensure data directory exists
    db_path = os.environ.get("DB_PATH", os.path.join(ROOT, "data", "semijobs.db"))
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    init_db()
    all_jobs = []
    has_api_keys = bool(os.environ.get("JSEARCH_API_KEY") or os.environ.get("ADZUNA_APP_ID"))

    if has_api_keys:
        # Use a subset of queries to stay within free tier limits
        queries_to_use = SEARCH_QUERIES[:5]
        for query in queries_to_use:
            try:
                all_jobs.extend(scrape_jsearch(query))
            except Exception as e:
                print(f"[JSearch] Failed for '{query}': {e}")
            time.sleep(1)
            try:
                all_jobs.extend(scrape_adzuna(query))
            except Exception as e:
                print(f"[Adzuna] Failed for '{query}': {e}")
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
    try:
        total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        fresher = conn.execute("SELECT COUNT(*) FROM jobs WHERE fresher_suitable=1").fetchone()[0]
        print(f"  Total jobs in DB: {total}")
        print(f"  Fresher suitable: {fresher}")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] Scraper failed: {e}")
        sys.exit(1)
