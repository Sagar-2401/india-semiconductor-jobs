"""Resume Analyzer — ATS Score + Role-Based Feedback for Semiconductor Resumes."""
import re
import io
import math
from collections import Counter

# Reuse domain keywords from classifier
DOMAIN_KEYWORDS = {
    "VLSI": ["vlsi", "verilog", "systemverilog", "synthesis", "netlist", "standard cell", "liberty",
             "gate level", "rtl to gds", "chip design", "ic design", "tapeout", "tape-out"],
    "RTL Design": ["rtl", "verilog", "vhdl", "systemverilog", "hdl", "logic design",
                   "register transfer", "microarchitecture"],
    "Physical Design": ["physical design", "floorplan", "placement", "routing", "cts",
                        "clock tree", "power grid", "ir drop", "p&r", "place and route",
                        "innovus", "icc2", "aprisa"],
    "STA": ["static timing", "sta ", "timing closure", "setup hold", "timing analysis",
            "primetime", "tempus", "slack", "timing constraint", "sdc"],
    "DFT": ["dft", "design for test", "scan chain", "atpg", "bist", "jtag", "boundary scan",
            "mbist", "test pattern", "tessent"],
    "Verification": ["verification", "uvm", "testbench", "formal verification", "simulation",
                     "coverage", "assertion", "systemverilog", "cocotb", "emulation"],
    "FPGA": ["fpga", "vivado", "quartus", "xilinx", "altera", "lattice", "programmable logic",
             "bitstream", "hls", "vitis"],
    "Embedded Systems": ["embedded", "firmware", "rtos", "microcontroller", "mcu", "bare-metal",
                         "arm cortex", "stm32", "esp32", "i2c", "spi", "uart", "gpio",
                         "embedded linux", "yocto", "device driver"],
    "Hardware Design": ["hardware design", "pcb", "schematic", "board design", "signal integrity",
                        "power supply", "hardware engineer", "hw engineer", "electronics design"],
    "AI Hardware": ["ai accelerator", "neural network", "inference", "npu", "tpu", "ai chip",
                    "machine learning hardware", "edge ai", "neuromorphic"],
    "Networking Silicon": ["networking", "switch silicon", "router silicon", "ethernet",
                           "asic networking", "pcie", "serdes", "high-speed interface"],
    "SoC Architecture": ["soc", "system on chip", "soc architecture", "noc", "bus architecture",
                         "amba", "axi", "interconnect", "subsystem"],
    "Analog/Mixed Signal": ["analog", "mixed signal", "adc", "dac", "pll", "ldo", "bandgap",
                            "op-amp", "comparator", "data converter", "rf design", "cmos analog"],
    "Processor Design": ["processor design", "cpu design", "risc-v", "instruction set",
                         "pipeline", "branch predictor", "cache design", "gpu architecture"],
}

# ATS-critical sections
ATS_SECTIONS = {
    "contact": ["email", "phone", "mobile", "linkedin", "github", "address"],
    "education": ["education", "academic", "degree", "university", "college", "bachelor", "master",
                  "b.tech", "m.tech", "b.e.", "m.e.", "btech", "mtech", "phd"],
    "experience": ["experience", "work history", "employment", "internship", "intern",
                   "professional experience", "work experience"],
    "skills": ["skills", "technical skills", "core competencies", "proficiencies",
               "tools", "technologies", "programming"],
    "projects": ["projects", "academic projects", "personal projects", "key projects",
                 "major projects", "project work"],
    "certifications": ["certifications", "certificates", "courses", "training",
                       "professional development"],
    "achievements": ["achievements", "awards", "honors", "accomplishments", "publications"],
}

# EDA tools and semiconductor-specific tools
SEMICONDUCTOR_TOOLS = [
    "cadence", "synopsys", "mentor", "siemens eda", "ansys",
    "virtuoso", "spectre", "innovus", "genus", "tempus", "primetime",
    "icc2", "dc compiler", "formality", "vcs", "verdi", "spyglass",
    "vivado", "quartus", "modelsim", "questasim",
    "magic", "klayout", "ngspice", "xschem",
    "matlab", "simulink", "python", "perl", "tcl",
    "git", "linux", "make", "cmake",
]


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    except Exception as e:
        raise ValueError(f"Could not parse PDF: {e}")


def get_page_count(pdf_bytes: bytes) -> int:
    """Get number of pages in PDF."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            return len(pdf.pages)
    except Exception:
        return 0


# ─── ATS SCORE (100 points) ─────────────────────────────────────────────────

def calculate_ats_score(pdf_bytes: bytes) -> dict:
    """Calculate ATS compatibility score (0-100) with category breakdown."""
    text = extract_text_from_pdf(pdf_bytes)
    text_lower = text.lower()
    pages = get_page_count(pdf_bytes)
    words = text.split()
    word_count = len(words)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    breakdown = {}
    suggestions = []

    # 1. FORMATTING (20 pts) — is it parseable text?
    fmt_score = 0
    if word_count > 50:
        fmt_score += 8  # Has meaningful text content
    elif word_count > 20:
        fmt_score += 4
    else:
        suggestions.append("Your resume has very little parseable text. Avoid image-based resumes.")

    # Check for consistent structure (lines with reasonable length)
    avg_line_len = sum(len(l) for l in lines) / max(len(lines), 1)
    if 20 < avg_line_len < 200:
        fmt_score += 6
    elif avg_line_len > 0:
        fmt_score += 3

    # No excessive special characters (tables, weird formatting)
    special_ratio = sum(1 for c in text if c in "│┌┐└┘─┼╌╎■□●○▪▫") / max(word_count, 1)
    if special_ratio < 0.01:
        fmt_score += 6
    else:
        fmt_score += 2
        suggestions.append("Simplify formatting — avoid tables/columns that confuse ATS parsers.")

    breakdown["formatting"] = min(fmt_score, 20)

    # 2. CONTACT INFO (10 pts)
    contact_score = 0
    if re.search(r'[\w.-]+@[\w.-]+\.\w+', text):
        contact_score += 4
    else:
        suggestions.append("Add a clearly visible email address at the top.")
    if re.search(r'(\+\d{1,3}[-.\s]?)?\(?\d{3,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}', text):
        contact_score += 3
    else:
        suggestions.append("Add your phone number in the contact section.")
    if "linkedin" in text_lower:
        contact_score += 3
    else:
        suggestions.append("Add your LinkedIn profile URL.")
    breakdown["contact_info"] = min(contact_score, 10)

    # 3. SECTION STRUCTURE (20 pts)
    section_score = 0
    found_sections = []
    critical_sections = ["education", "experience", "skills", "projects"]
    for section_name, keywords in ATS_SECTIONS.items():
        if any(kw in text_lower for kw in keywords):
            found_sections.append(section_name)

    for cs in critical_sections:
        if cs in found_sections:
            section_score += 4
        else:
            suggestions.append(f"Add a clear '{cs.title()}' section heading.")

    if len(found_sections) >= 5:
        section_score += 4  # Bonus for extra sections
    breakdown["sections"] = min(section_score, 20)

    # 4. KEYWORD DENSITY (25 pts)
    keyword_score = 0
    all_semi_keywords = []
    for keywords in DOMAIN_KEYWORDS.values():
        all_semi_keywords.extend(keywords)
    all_semi_keywords.extend(SEMICONDUCTOR_TOOLS)
    all_semi_keywords = list(set(all_semi_keywords))

    matched_keywords = [kw for kw in all_semi_keywords if kw in text_lower]
    kw_count = len(matched_keywords)

    if kw_count >= 20:
        keyword_score = 25
    elif kw_count >= 15:
        keyword_score = 22
    elif kw_count >= 10:
        keyword_score = 18
    elif kw_count >= 5:
        keyword_score = 12
    elif kw_count >= 2:
        keyword_score = 6
    else:
        keyword_score = 0
        suggestions.append("Add more semiconductor-specific technical keywords to your resume.")
    breakdown["keywords"] = keyword_score

    # 5. LENGTH & CONTENT (15 pts)
    length_score = 0
    if pages == 1:
        length_score += 8  # Perfect for freshers
    elif pages == 2:
        length_score += 6
    elif pages > 2:
        length_score += 2
        suggestions.append("Keep your resume to 1-2 pages for better ATS processing.")
    
    # Bullet points (ATS loves them)
    bullet_lines = sum(1 for l in lines if l.startswith(("•", "-", "–", "▪", "*", "►")))
    if bullet_lines >= 8:
        length_score += 7
    elif bullet_lines >= 4:
        length_score += 5
    elif bullet_lines >= 1:
        length_score += 2
    else:
        suggestions.append("Use bullet points (•) to describe experiences — ATS parsers handle them well.")
    breakdown["length_content"] = min(length_score, 15)

    # 6. QUANTIFICATION (10 pts)
    quant_score = 0
    numbers = re.findall(r'\d+[\+%]', text)
    metrics = re.findall(r'(?:improved|reduced|increased|enhanced|optimized|achieved|saved|delivered)\s+(?:by\s+)?\d', text_lower)
    
    if len(numbers) >= 5:
        quant_score = 10
    elif len(numbers) >= 3:
        quant_score = 7
    elif len(numbers) >= 1:
        quant_score = 4
    else:
        quant_score = 0

    if not metrics and quant_score < 7:
        suggestions.append("Quantify your achievements (e.g., 'Improved timing closure by 15%', 'Reduced area by 10%').")
    breakdown["quantification"] = min(quant_score, 10)

    total = sum(breakdown.values())

    # Overall rating
    if total >= 80:
        rating = "Excellent"
    elif total >= 65:
        rating = "Good"
    elif total >= 50:
        rating = "Fair"
    else:
        rating = "Needs Improvement"

    return {
        "total_score": total,
        "max_score": 100,
        "rating": rating,
        "breakdown": breakdown,
        "suggestions": suggestions[:8],  # Limit suggestions
        "stats": {
            "pages": pages,
            "word_count": word_count,
            "keywords_found": kw_count,
            "sections_found": len(found_sections),
            "bullet_points": bullet_lines,
        }
    }


# ─── ROLE MATCH ANALYSIS ────────────────────────────────────────────────────

def analyze_resume_for_role(pdf_bytes: bytes, target_role: str) -> dict:
    """Analyze resume fit for a specific semiconductor role."""
    text = extract_text_from_pdf(pdf_bytes)
    text_lower = text.lower()

    # Get keywords for the target role
    role_keywords = DOMAIN_KEYWORDS.get(target_role, [])
    if not role_keywords:
        # Try fuzzy matching
        for domain, keywords in DOMAIN_KEYWORDS.items():
            if target_role.lower() in domain.lower() or domain.lower() in target_role.lower():
                role_keywords = keywords
                target_role = domain
                break

    if not role_keywords:
        role_keywords = []
        for keywords in DOMAIN_KEYWORDS.values():
            role_keywords.extend(keywords)
        target_role = "General Semiconductor"

    # Check which role keywords are matched
    matched_skills = [kw for kw in role_keywords if kw in text_lower]
    missing_skills = [kw for kw in role_keywords if kw not in text_lower]

    # Check tools
    matched_tools = [t for t in SEMICONDUCTOR_TOOLS if t in text_lower]

    # Score calculation
    if role_keywords:
        skill_match_pct = round(len(matched_skills) / len(role_keywords) * 100)
    else:
        skill_match_pct = 0

    # Role fit score (1-10)
    role_fit = min(10, max(1, round(skill_match_pct / 10)))

    # Check for related domains (cross-domain skills are valuable)
    cross_domain_skills = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if domain != target_role:
            cross_matches = [kw for kw in keywords if kw in text_lower]
            if cross_matches:
                cross_domain_skills[domain] = cross_matches[:3]

    # Generate role-specific suggestions
    suggestions = []
    if skill_match_pct < 30:
        suggestions.append(f"Your resume has very few {target_role} keywords. Focus on adding relevant technical terms.")
    elif skill_match_pct < 60:
        suggestions.append(f"Good start! Add more {target_role}-specific terminology to strengthen your profile.")

    if missing_skills:
        top_missing = missing_skills[:5]
        suggestions.append(f"Consider adding experience with: {', '.join(top_missing)}")

    if not matched_tools:
        suggestions.append("Mention specific EDA tools you've used (e.g., Cadence Virtuoso, Synopsys VCS, Vivado).")
    elif len(matched_tools) < 3:
        suggestions.append("List more industry tools in a dedicated 'Tools & Technologies' section.")

    # Check for projects
    if "project" not in text_lower:
        suggestions.append(f"Add {target_role}-related projects to demonstrate hands-on experience.")

    # Check for education keywords
    edu_keywords = ["b.tech", "m.tech", "btech", "mtech", "bachelor", "master", "ece", "eee",
                    "electronics", "electrical", "computer science", "vlsi", "microelectronics"]
    has_relevant_edu = any(e in text_lower for e in edu_keywords)
    if not has_relevant_edu:
        suggestions.append("Highlight your Electronics/VLSI/EE degree prominently.")

    # Strength areas
    strengths = []
    if skill_match_pct >= 60:
        strengths.append(f"Strong {target_role} keyword coverage ({skill_match_pct}%)")
    if len(matched_tools) >= 3:
        strengths.append(f"Good EDA tool knowledge ({len(matched_tools)} tools mentioned)")
    if cross_domain_skills:
        domains = list(cross_domain_skills.keys())[:3]
        strengths.append(f"Cross-domain skills in: {', '.join(domains)}")
    if has_relevant_edu:
        strengths.append("Relevant educational background detected")

    return {
        "target_role": target_role,
        "role_fit_score": role_fit,
        "skill_match_percentage": skill_match_pct,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills[:8],
        "matched_tools": matched_tools,
        "cross_domain_skills": cross_domain_skills,
        "strengths": strengths,
        "suggestions": suggestions[:6],
    }


def full_resume_analysis(pdf_bytes: bytes, target_role: str = "VLSI") -> dict:
    """Perform complete resume analysis: ATS score + role match."""
    ats = calculate_ats_score(pdf_bytes)
    role = analyze_resume_for_role(pdf_bytes, target_role)
    return {
        "ats": ats,
        "role_match": role,
    }
