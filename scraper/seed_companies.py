import os
import sys
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.database import init_db, insert_company, get_db

def seed_companies():
    md_file = r"C:\Users\sagar\.gemini\antigravity\brain\5b2d8df6-b024-42f1-826d-d439c3db847e\india_semiconductor_database.md"
    if not os.path.exists(md_file):
        print(f"File not found: {md_file}")
        return

    with open(md_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    init_db()
    inserted = 0

    for line in lines:
        if line.strip().startswith("|") and not "---" in line and not "Company" in line and not "Total" in line and not "Category" in line.split("|")[1]:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 7:
                try:
                    num = int(parts[1])  # Ensure it's a row with a number
                except ValueError:
                    continue
                
                name = parts[2]
                hq = parts[3]
                locations = parts[4]
                category = parts[5]
                description = parts[6]

                # Map some domains roughly from category/description to match the frontend colors
                domains = []
                low_cat = (category + description).lower()
                if "vlsi" in low_cat or "rtl" in low_cat or "asic" in low_cat or "soc" in low_cat: domains.append("VLSI")
                if "fpga" in low_cat: domains.append("FPGA")
                if "embedded" in low_cat or "firmware" in low_cat: domains.append("Embedded Systems")
                if "analog" in low_cat or "mixed-signal" in low_cat: domains.append("Analog/Mixed Signal")
                if "ai" in low_cat: domains.append("AI Hardware")
                if "verification" in low_cat: domains.append("Verification")
                if "dft" in low_cat: domains.append("DFT")
                if "rf" in low_cat or "microwave" in low_cat: domains.append("Analog/Mixed Signal")
                if "automotive" in low_cat: domains.append("Embedded Systems")
                if "manufacturing" in low_cat or "fab" in low_cat or "osat" in low_cat or "test" in low_cat: domains.append("Hardware Design")

                if not domains:
                    domains.append("Hardware Design")
                
                # Assign some deterministic dummy values for fresher scores and salaries based on name hash
                score = (hash(name) % 3) + 3 # 3-5
                min_sal = (hash(name) % 10) + 5
                max_sal = min_sal + (hash(name) % 15) + 5

                company_data = {
                    "name": name,
                    "hq_country": hq,
                    "india_locations": locations,
                    "category": category,
                    "job_domains": ",".join(list(set(domains))),
                    "description": description,
                    "fresher_salary_min": min_sal,
                    "fresher_salary_max": max_sal,
                    "fresher_score": score
                }

                if insert_company(company_data):
                    inserted += 1

    print(f"[DONE] Seeded {inserted} companies into the database.")

if __name__ == "__main__":
    seed_companies()
