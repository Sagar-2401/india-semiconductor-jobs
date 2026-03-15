"""Resume Analyzer — Company-Level ATS + AI Filter Bypass for Semiconductor Resumes.

Simulates real ATS systems (Workday, Taleo, SuccessFactors, Greenhouse) and
AI-based hiring filters used by top semiconductor companies. Checks exact
keyword matching, skill synonyms, and company-specific requirements.
"""
import re
import io
import math
from collections import Counter

# ─── DOMAIN KEYWORDS (reused from classifier) ───────────────────────────────

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

# ─── ATS-CRITICAL SECTIONS ──────────────────────────────────────────────────

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

# ─── SEMICONDUCTOR TOOLS ────────────────────────────────────────────────────

SEMICONDUCTOR_TOOLS = [
    "cadence", "synopsys", "mentor", "siemens eda", "ansys",
    "virtuoso", "spectre", "innovus", "genus", "tempus", "primetime",
    "icc2", "dc compiler", "formality", "vcs", "verdi", "spyglass",
    "vivado", "quartus", "modelsim", "questasim",
    "magic", "klayout", "ngspice", "xschem",
    "matlab", "simulink", "python", "perl", "tcl",
    "git", "linux", "make", "cmake",
    # Additional power tools
    "redhawk", "voltus", "totem",
    # Formal / CDC
    "jasper", "questa", "conformal",
    # Layout
    "calibre", "assura", "pegasus", "icv",
    # FPGA/IP
    "vitis", "petalinux", "platform cable",
    # Scripting
    "shell script", "bash", "awk", "sed",
]

# ─── KEYWORD SYNONYMS (AI filters & ATS match these interchangeably) ────────

KEYWORD_SYNONYMS = {
    "verilog": ["verilog", "verilog hdl", "ieee 1364"],
    "systemverilog": ["systemverilog", "system verilog", "sv", "ieee 1800"],
    "vhdl": ["vhdl", "ieee 1076"],
    "uvm": ["uvm", "universal verification methodology", "ovm"],
    "synthesis": ["synthesis", "logic synthesis", "rtl synthesis", "design synthesis"],
    "static timing": ["static timing analysis", "sta", "timing analysis", "timing closure",
                      "setup time", "hold time", "setup and hold"],
    "physical design": ["physical design", "pd", "backend design", "place and route",
                        "apr", "p&r", "pnr"],
    "dft": ["dft", "design for test", "design for testability", "design-for-test"],
    "fpga": ["fpga", "field programmable gate array", "field-programmable"],
    "asic": ["asic", "application specific integrated circuit", "application-specific"],
    "soc": ["soc", "system on chip", "system-on-chip"],
    "rtl": ["rtl", "register transfer level", "register-transfer level"],
    "floorplan": ["floorplan", "floorplanning", "floor plan", "floor planning"],
    "clock tree": ["clock tree synthesis", "cts", "clock tree", "clock network"],
    "place and route": ["place and route", "placement and routing", "p&r", "pnr", "apr"],
    "scan chain": ["scan chain", "scan insertion", "scan stitching", "scan design"],
    "formal verification": ["formal verification", "formal methods", "model checking",
                            "property checking", "equivalence checking"],
    "coverage": ["code coverage", "functional coverage", "coverage driven", "coverage closure",
                 "statement coverage", "branch coverage", "toggle coverage"],
    "timing constraint": ["timing constraint", "sdc", "synopsys design constraints",
                          "timing exceptions", "false path", "multicycle path"],
    "power analysis": ["power analysis", "power estimation", "dynamic power", "leakage power",
                       "ir drop", "power grid"],
    "signal integrity": ["signal integrity", "si", "crosstalk", "noise analysis", "em",
                         "electromigration"],
    "layout": ["layout", "custom layout", "full custom", "mask layout", "gdsii", "gds"],
    "pcb": ["pcb", "printed circuit board", "board layout", "pcb design"],
    "embedded": ["embedded systems", "embedded software", "embedded firmware",
                 "embedded programming"],
    "rtos": ["rtos", "real-time operating system", "freertos", "vxworks", "zephyr"],
    "arm": ["arm", "arm cortex", "cortex-m", "cortex-a", "cortex-r", "arm architecture"],
    "risc-v": ["risc-v", "riscv", "risc v", "risc-v isa"],
    "pll": ["pll", "phase locked loop", "phase-locked loop"],
    "adc": ["adc", "analog to digital", "analog-to-digital converter", "a/d converter"],
    "dac": ["dac", "digital to analog", "digital-to-analog converter", "d/a converter"],
    "pcie": ["pcie", "pci express", "pci-express", "pci-e"],
    "serdes": ["serdes", "serializer deserializer", "serial deserial"],
    "amba": ["amba", "axi", "ahb", "apb", "ace", "chi"],
}

# ─── COMPANY-SPECIFIC ATS PROFILES ──────────────────────────────────────────
# Real requirements extracted from actual job postings of each company

COMPANY_ATS_PROFILES = {
    "Intel": {
        "ats_system": "Workday",
        "must_have": ["verilog", "systemverilog", "python", "linux"],
        "strong_plus": ["uvm", "synthesis", "formal verification", "emulation",
                        "power analysis", "clock domain crossing", "cdc", "rdc",
                        "low power", "upf", "cpf"],
        "tools": ["synopsys", "cadence", "mentor", "git", "perforce"],
        "soft_skills": ["problem solving", "teamwork", "communication", "agile", "scrum"],
        "education": ["b.tech", "m.tech", "ms", "phd", "ece", "ee", "computer science"],
        "process_nodes": ["7nm", "5nm", "3nm", "intel 4", "intel 3", "intel 18a", "finfet", "gaafet"],
        "buzzwords": ["full chip", "ip level", "block level", "soc integration",
                      "silicon validation", "post-silicon", "pre-silicon"],
    },
    "AMD": {
        "ats_system": "Workday",
        "must_have": ["verilog", "systemverilog", "python"],
        "strong_plus": ["rtl", "synthesis", "uvm", "physical design", "timing closure",
                        "performance analysis", "gpu", "cpu", "cache", "memory controller"],
        "tools": ["synopsys", "cadence", "vcs", "verdi", "dc compiler", "primetime",
                  "innovus", "icc2", "git"],
        "soft_skills": ["collaboration", "innovation", "problem solving"],
        "education": ["b.tech", "m.tech", "ms", "phd", "ece", "electrical"],
        "process_nodes": ["5nm", "4nm", "3nm", "tsmc", "advanced node"],
        "buzzwords": ["zen", "rdna", "cdna", "chiplet", "infinity fabric",
                      "high performance computing", "hpc"],
    },
    "Qualcomm": {
        "ats_system": "Workday",
        "must_have": ["verilog", "systemverilog", "c", "c++"],
        "strong_plus": ["arm", "soc", "modem", "5g", "wireless", "dsp", "gpu",
                        "low power", "power management", "camera", "multimedia"],
        "tools": ["synopsys", "cadence", "python", "perl", "tcl", "git", "linux"],
        "soft_skills": ["innovation", "5g leadership", "mobile", "wireless"],
        "education": ["b.tech", "m.tech", "ms", "phd", "ece", "eee"],
        "process_nodes": ["4nm", "5nm", "7nm", "snapdragon"],
        "buzzwords": ["snapdragon", "mobile platform", "iot", "automotive",
                      "connectivity", "wi-fi", "bluetooth"],
    },
    "NVIDIA": {
        "ats_system": "Workday",
        "must_have": ["verilog", "systemverilog", "python", "c++"],
        "strong_plus": ["gpu", "cuda", "ai", "deep learning", "rtl", "uvm",
                        "architecture", "performance", "memory", "interconnect"],
        "tools": ["synopsys", "cadence", "vcs", "verdi", "python", "git", "linux"],
        "soft_skills": ["innovation", "ai passion", "problem solving"],
        "education": ["b.tech", "m.tech", "ms", "phd", "computer science", "ece"],
        "process_nodes": ["5nm", "4nm", "3nm", "tsmc", "samsung"],
        "buzzwords": ["gpu architecture", "tensor core", "ray tracing", "ai accelerator",
                      "data center", "autonomous driving", "grace hopper"],
    },
    "Texas Instruments": {
        "ats_system": "Workday",
        "must_have": ["analog", "mixed signal", "circuit design"],
        "strong_plus": ["pll", "adc", "dac", "ldo", "bandgap", "op-amp", "power management",
                        "cmos", "bicmos", "high voltage", "automotive"],
        "tools": ["cadence", "virtuoso", "spectre", "hspice", "calibre", "matlab"],
        "soft_skills": ["customer focus", "quality", "innovation"],
        "education": ["b.tech", "m.tech", "ms", "phd", "ece", "electronics"],
        "process_nodes": ["28nm", "65nm", "130nm", "bcd", "high voltage"],
        "buzzwords": ["analog signal chain", "power management", "automotive grade",
                      "industrial", "embedded processing"],
    },
    "Synopsys": {
        "ats_system": "Workday",
        "must_have": ["eda", "algorithm", "c++", "python"],
        "strong_plus": ["synthesis", "place and route", "sta", "formal verification",
                        "simulation", "emulation", "dft", "power analysis"],
        "tools": ["dc compiler", "icc2", "primetime", "vcs", "formality", "spyglass",
                  "genus", "innovus", "python", "tcl"],
        "soft_skills": ["software engineering", "algorithm design", "customer support"],
        "education": ["b.tech", "m.tech", "ms", "phd", "computer science", "ece"],
        "process_nodes": ["3nm", "2nm", "gaa", "finfet", "multi-die"],
        "buzzwords": ["eda", "design automation", "silicon lifecycle", "ai-driven eda",
                      "multi-die", "3d-ic", "chiplet"],
    },
    "Cadence": {
        "ats_system": "Workday",
        "must_have": ["eda", "c++", "algorithm"],
        "strong_plus": ["analog simulation", "digital implementation", "verification",
                        "custom layout", "mixed signal", "rf", "pcb", "system analysis"],
        "tools": ["virtuoso", "spectre", "innovus", "genus", "tempus", "xcelium",
                  "jasper", "conformal", "python", "tcl"],
        "soft_skills": ["innovation", "customer collaboration"],
        "education": ["b.tech", "m.tech", "ms", "phd", "ece", "computer science"],
        "process_nodes": ["3nm", "2nm", "finfet", "gaa"],
        "buzzwords": ["intelligent system design", "computational software",
                      "multi-physics", "digital twin"],
    },
    "Samsung": {
        "ats_system": "SuccessFactors",
        "must_have": ["verilog", "systemverilog", "semiconductor"],
        "strong_plus": ["memory", "sram", "dram", "nand", "logic", "foundry",
                        "process technology", "device physics"],
        "tools": ["synopsys", "cadence", "hspice", "calibre", "python"],
        "soft_skills": ["teamwork", "global collaboration"],
        "education": ["b.tech", "m.tech", "ms", "phd", "ece", "material science"],
        "process_nodes": ["3nm", "2nm", "gaa", "mbcfet", "exynos"],
        "buzzwords": ["foundry", "gaa", "mbcfet", "hbm", "exynos",
                      "memory technology", "3d nand"],
    },
    "Broadcom": {
        "ats_system": "Workday",
        "must_have": ["verilog", "systemverilog", "networking"],
        "strong_plus": ["ethernet", "switch", "router", "serdes", "pcie", "storage",
                        "asic", "high speed interface", "broadband"],
        "tools": ["synopsys", "cadence", "vcs", "innovus", "python", "perl"],
        "soft_skills": ["networking knowledge", "system understanding"],
        "education": ["b.tech", "m.tech", "ms", "ece", "computer science"],
        "process_nodes": ["5nm", "7nm", "advanced"],
        "buzzwords": ["switch silicon", "asic", "networking", "storage",
                      "broadband", "enterprise", "data center"],
    },
    "Tata Elxsi": {
        "ats_system": "Taleo",
        "must_have": ["vlsi", "embedded", "automotive"],
        "strong_plus": ["fpga", "rtl", "verification", "autosar", "can", "lin",
                        "adas", "infotainment", "v2x"],
        "tools": ["vivado", "quartus", "cadence", "matlab", "simulink", "python", "c"],
        "soft_skills": ["customer management", "team collaboration"],
        "education": ["b.tech", "m.tech", "ece", "eee", "electronics"],
        "process_nodes": [],
        "buzzwords": ["design-led", "technology services", "automotive electronics",
                      "medical devices", "broadcast"],
    },
    "Wipro": {
        "ats_system": "Workday",
        "must_have": ["vlsi", "verification", "rtl"],
        "strong_plus": ["uvm", "systemverilog", "synthesis", "physical design",
                        "sta", "dft", "emulation"],
        "tools": ["synopsys", "cadence", "mentor", "python", "perl"],
        "soft_skills": ["client interaction", "agile", "teamwork"],
        "education": ["b.tech", "m.tech", "ece", "eee"],
        "process_nodes": [],
        "buzzwords": ["vlsi services", "semiconductor services", "asic design services"],
    },
    "HCL": {
        "ats_system": "Taleo",
        "must_have": ["vlsi", "asic", "rtl"],
        "strong_plus": ["synthesis", "physical design", "dft", "sta", "verification",
                        "uvm", "low power", "cdc"],
        "tools": ["synopsys", "cadence", "mentor", "innovus", "dc compiler", "python"],
        "soft_skills": ["communication", "problem solving"],
        "education": ["b.tech", "m.tech", "ece", "eee"],
        "process_nodes": ["7nm", "5nm", "advanced node"],
        "buzzwords": ["engineering services", "semiconductor design"],
    },
}

# ─── ACTION VERBS — ATS AI filters love these ────────────────────────────────

ACTION_VERBS = [
    "designed", "developed", "implemented", "optimized", "analyzed", "debugged",
    "verified", "validated", "automated", "architected", "integrated", "configured",
    "synthesized", "simulated", "characterized", "measured", "reduced", "improved",
    "achieved", "led", "managed", "collaborated", "presented", "documented",
    "reviewed", "mentored", "trained", "delivered", "resolved", "enhanced",
]


# ─── PDF EXTRACTION ─────────────────────────────────────────────────────────

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


# ─── SYNONYM-AWARE KEYWORD MATCHING ─────────────────────────────────────────

def check_keyword_with_synonyms(keyword: str, text_lower: str) -> tuple:
    """Check if a keyword or any of its synonyms exist in the text.
    Returns (found: bool, matched_variant: str or None)."""
    if keyword in text_lower:
        return True, keyword
    # Check synonym variations
    for base_kw, synonyms in KEYWORD_SYNONYMS.items():
        if keyword in synonyms or keyword == base_kw:
            for syn in synonyms:
                if syn in text_lower:
                    return True, syn
    return False, None


def count_keyword_variants(keyword: str, text_lower: str) -> int:
    """Count total occurrences of a keyword including all synonym forms."""
    count = text_lower.count(keyword)
    for base_kw, synonyms in KEYWORD_SYNONYMS.items():
        if keyword in synonyms or keyword == base_kw:
            for syn in synonyms:
                if syn != keyword:
                    count += text_lower.count(syn)
    return count


# ─── COMPANY ATS ANALYSIS ───────────────────────────────────────────────────

def analyze_company_ats(text_lower: str, company: str) -> dict:
    """Analyze resume against a specific company's ATS profile."""
    profile = COMPANY_ATS_PROFILES.get(company)
    if not profile:
        return None

    result = {
        "company": company,
        "ats_system": profile["ats_system"],
        "pass_probability": 0,
        "must_have_matched": [],
        "must_have_missing": [],
        "strong_plus_matched": [],
        "strong_plus_missing": [],
        "tools_matched": [],
        "tools_missing": [],
        "buzzwords_matched": [],
        "education_match": False,
        "process_nodes_matched": [],
        "action_verbs_count": 0,
    }

    # Must-have keywords (critical — missing these = auto-reject by ATS)
    for kw in profile["must_have"]:
        found, variant = check_keyword_with_synonyms(kw, text_lower)
        if found:
            result["must_have_matched"].append(variant or kw)
        else:
            result["must_have_missing"].append(kw)

    # Strong-plus keywords
    for kw in profile["strong_plus"]:
        found, variant = check_keyword_with_synonyms(kw, text_lower)
        if found:
            result["strong_plus_matched"].append(variant or kw)
        else:
            result["strong_plus_missing"].append(kw)

    # Tools
    for tool in profile["tools"]:
        if tool in text_lower:
            result["tools_matched"].append(tool)
        else:
            result["tools_missing"].append(tool)

    # Education keywords
    for edu in profile.get("education", []):
        if edu in text_lower:
            result["education_match"] = True
            break

    # Process nodes / technology
    for node in profile.get("process_nodes", []):
        if node in text_lower:
            result["process_nodes_matched"].append(node)

    # Buzzwords
    for bw in profile.get("buzzwords", []):
        if bw in text_lower:
            result["buzzwords_matched"].append(bw)

    # Action verbs count
    result["action_verbs_count"] = sum(1 for v in ACTION_VERBS if v in text_lower)

    # Calculate pass probability
    must_have_total = len(profile["must_have"])
    must_have_hit = len(result["must_have_matched"])
    strong_total = len(profile["strong_plus"])
    strong_hit = len(result["strong_plus_matched"])
    tools_total = len(profile["tools"])
    tools_hit = len(result["tools_matched"])

    # Must-haves are critical (50% weight)
    must_score = (must_have_hit / max(must_have_total, 1)) * 50
    # Strong-plus (25% weight)
    strong_score = (strong_hit / max(strong_total, 1)) * 25
    # Tools (15% weight)
    tools_score = (tools_hit / max(tools_total, 1)) * 15
    # Education + action verbs + buzzwords (10% weight)
    bonus = 0
    if result["education_match"]:
        bonus += 4
    if result["action_verbs_count"] >= 5:
        bonus += 3
    elif result["action_verbs_count"] >= 2:
        bonus += 1
    if result["buzzwords_matched"]:
        bonus += 3

    result["pass_probability"] = min(100, round(must_score + strong_score + tools_score + bonus))

    return result


# ─── ATS SCORE (100 points) — ENHANCED ──────────────────────────────────────

def calculate_ats_score(pdf_bytes: bytes) -> dict:
    """Calculate ATS compatibility score (0-100) with category breakdown.
    Simulates real ATS parsing behavior of Workday/Taleo/SuccessFactors."""
    text = extract_text_from_pdf(pdf_bytes)
    text_lower = text.lower()
    pages = get_page_count(pdf_bytes)
    words = text.split()
    word_count = len(words)
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    breakdown = {}
    suggestions = []

    # 1. FORMATTING & PARSABILITY (20 pts)
    fmt_score = 0
    if word_count > 50:
        fmt_score += 8
    elif word_count > 20:
        fmt_score += 4
    else:
        suggestions.append("Your resume has very little parseable text. Avoid image-based resumes — ATS cannot read images.")

    avg_line_len = sum(len(l) for l in lines) / max(len(lines), 1)
    if 20 < avg_line_len < 200:
        fmt_score += 6
    elif avg_line_len > 0:
        fmt_score += 3

    special_ratio = sum(1 for c in text if c in "│┌┐└┘─┼╌╎■□●○▪▫") / max(word_count, 1)
    if special_ratio < 0.01:
        fmt_score += 6
    else:
        fmt_score += 2
        suggestions.append("Simplify formatting — ATS like Workday and Taleo choke on tables/columns/graphics.")

    breakdown["formatting"] = min(fmt_score, 20)

    # 2. CONTACT INFO (10 pts)
    contact_score = 0
    if re.search(r'[\w.-]+@[\w.-]+\.\w+', text):
        contact_score += 4
    else:
        suggestions.append("Add a clearly visible email address — ATS auto-extract this as primary contact.")
    if re.search(r'(\+\d{1,3}[-.\s]?)?\(?\d{3,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}', text):
        contact_score += 3
    else:
        suggestions.append("Add your phone number — every ATS requires this field.")
    if "linkedin" in text_lower:
        contact_score += 3
    else:
        suggestions.append("Add your LinkedIn profile URL — recruiters cross-reference this via ATS.")
    breakdown["contact_info"] = min(contact_score, 10)

    # 3. SECTION STRUCTURE (15 pts) — ATS maps content by section headings
    section_score = 0
    found_sections = []
    critical_sections = ["education", "experience", "skills", "projects"]
    for section_name, keywords in ATS_SECTIONS.items():
        if any(kw in text_lower for kw in keywords):
            found_sections.append(section_name)

    for cs in critical_sections:
        if cs in found_sections:
            section_score += 3
        else:
            suggestions.append(f"Add a clear '{cs.title()}' section — ATS maps your data by section headings.")

    if len(found_sections) >= 5:
        section_score += 3
    breakdown["sections"] = min(section_score, 15)

    # 4. KEYWORD DENSITY & SYNONYM COVERAGE (25 pts)
    keyword_score = 0
    all_semi_keywords = []
    for keywords in DOMAIN_KEYWORDS.values():
        all_semi_keywords.extend(keywords)
    all_semi_keywords.extend(SEMICONDUCTOR_TOOLS)
    all_semi_keywords = list(set(all_semi_keywords))

    matched_keywords = []
    for kw in all_semi_keywords:
        found, variant = check_keyword_with_synonyms(kw, text_lower)
        if found:
            matched_keywords.append(variant or kw)
    matched_keywords = list(set(matched_keywords))
    kw_count = len(matched_keywords)

    # Also check keyword repetition (ATS rank by frequency)
    keyword_frequency = {}
    for kw in matched_keywords[:20]:
        freq = count_keyword_variants(kw, text_lower)
        if freq > 0:
            keyword_frequency[kw] = freq

    high_freq_count = sum(1 for f in keyword_frequency.values() if f >= 2)

    if kw_count >= 25:
        keyword_score = 25
    elif kw_count >= 20:
        keyword_score = 23
    elif kw_count >= 15:
        keyword_score = 20
    elif kw_count >= 10:
        keyword_score = 16
    elif kw_count >= 5:
        keyword_score = 10
    elif kw_count >= 2:
        keyword_score = 5
    else:
        keyword_score = 0
        suggestions.append("Add semiconductor-specific keywords — ATS rank resumes by keyword match density.")

    if high_freq_count < 3 and kw_count > 5:
        suggestions.append("Repeat key skills 2-3 times naturally (in skills list + project descriptions) — AI filters rank by frequency.")

    breakdown["keywords"] = keyword_score

    # 5. ACTION VERBS & ACHIEVEMENTS (15 pts)
    action_score = 0
    found_verbs = [v for v in ACTION_VERBS if v in text_lower]
    numbers = re.findall(r'\d+[\+%]', text)
    metrics = re.findall(r'(?:improved|reduced|increased|enhanced|optimized|achieved|saved|delivered)\s+(?:by\s+)?\d', text_lower)

    if len(found_verbs) >= 10:
        action_score += 8
    elif len(found_verbs) >= 5:
        action_score += 5
    elif len(found_verbs) >= 2:
        action_score += 3
    else:
        suggestions.append("Start bullet points with action verbs (Designed, Implemented, Optimized) — AI filters score this.")

    if len(numbers) >= 5:
        action_score += 7
    elif len(numbers) >= 3:
        action_score += 5
    elif len(numbers) >= 1:
        action_score += 3
    else:
        suggestions.append("Quantify achievements (e.g., 'Reduced area by 15%', 'Achieved timing closure at 1GHz').")

    breakdown["action_impact"] = min(action_score, 15)

    # 6. LENGTH & BULLET STRUCTURE (15 pts)
    length_score = 0
    if pages == 1:
        length_score += 8
    elif pages == 2:
        length_score += 6
    elif pages > 2:
        length_score += 2
        suggestions.append("Keep resume 1-2 pages — Workday/Taleo parse longer resumes poorly.")

    bullet_lines = sum(1 for l in lines if l.startswith(("•", "-", "–", "▪", "*", "►")))
    if bullet_lines >= 10:
        length_score += 7
    elif bullet_lines >= 5:
        length_score += 5
    elif bullet_lines >= 2:
        length_score += 3
    else:
        suggestions.append("Use bullet points (•) — all ATS systems parse these more reliably than paragraphs.")
    breakdown["length_content"] = min(length_score, 15)

    total = sum(breakdown.values())

    if total >= 80:
        rating = "Excellent — Likely to pass most ATS filters"
    elif total >= 65:
        rating = "Good — Should pass standard ATS"
    elif total >= 50:
        rating = "Fair — May get filtered by strict ATS"
    else:
        rating = "Needs Improvement — High risk of ATS rejection"

    return {
        "total_score": total,
        "max_score": 100,
        "rating": rating,
        "breakdown": breakdown,
        "suggestions": suggestions[:10],
        "stats": {
            "pages": pages,
            "word_count": word_count,
            "keywords_found": kw_count,
            "keyword_frequency": dict(list(keyword_frequency.items())[:10]),
            "sections_found": len(found_sections),
            "bullet_points": bullet_lines,
            "action_verbs": len(found_verbs),
        }
    }


# ─── ROLE MATCH ANALYSIS ────────────────────────────────────────────────────

def analyze_resume_for_role(pdf_bytes: bytes, target_role: str) -> dict:
    """Analyze resume fit for a specific semiconductor role with synonym matching."""
    text = extract_text_from_pdf(pdf_bytes)
    text_lower = text.lower()

    role_keywords = DOMAIN_KEYWORDS.get(target_role, [])
    if not role_keywords:
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

    matched_skills = []
    missing_skills = []
    for kw in role_keywords:
        found, variant = check_keyword_with_synonyms(kw, text_lower)
        if found:
            matched_skills.append(variant or kw)
        else:
            missing_skills.append(kw)

    matched_tools = [t for t in SEMICONDUCTOR_TOOLS if t in text_lower]

    if role_keywords:
        skill_match_pct = round(len(matched_skills) / len(role_keywords) * 100)
    else:
        skill_match_pct = 0

    role_fit = min(10, max(1, round(skill_match_pct / 10)))

    cross_domain_skills = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if domain != target_role:
            cross_matches = [kw for kw in keywords if kw in text_lower]
            if cross_matches:
                cross_domain_skills[domain] = cross_matches[:3]

    suggestions = []
    if skill_match_pct < 30:
        suggestions.append(f"Your resume has very few {target_role} keywords. ATS will likely filter you out for this role.")
    elif skill_match_pct < 60:
        suggestions.append(f"Add more {target_role} keywords — aim for 60%+ coverage to pass AI screening.")

    if missing_skills:
        top_missing = missing_skills[:5]
        suggestions.append(f"Missing critical skills: {', '.join(top_missing)}")

    if not matched_tools:
        suggestions.append("Mention EDA tools explicitly — ATS requires exact tool name matches.")
    elif len(matched_tools) < 3:
        suggestions.append("Add more tools in a dedicated 'Tools & Technologies' section for ATS parsing.")

    if "project" not in text_lower:
        suggestions.append(f"Add {target_role} projects — AI filters look for hands-on experience evidence.")

    edu_keywords = ["b.tech", "m.tech", "btech", "mtech", "bachelor", "master", "ece", "eee",
                    "electronics", "electrical", "computer science", "vlsi", "microelectronics"]
    has_relevant_edu = any(e in text_lower for e in edu_keywords)
    if not has_relevant_edu:
        suggestions.append("Highlight your Electronics/VLSI/EE degree — ATS checks education field match.")

    strengths = []
    if skill_match_pct >= 60:
        strengths.append(f"Strong {target_role} keyword coverage ({skill_match_pct}%)")
    if len(matched_tools) >= 3:
        strengths.append(f"Good EDA tool knowledge ({len(matched_tools)} tools)")
    if cross_domain_skills:
        domains = list(cross_domain_skills.keys())[:3]
        strengths.append(f"Cross-domain skills: {', '.join(domains)}")
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


# ─── COMPANY-SPECIFIC BYPASS ANALYSIS ───────────────────────────────────────

def analyze_company_bypass(pdf_bytes: bytes, company: str = None) -> dict:
    """Analyze resume against specific company ATS or all top companies."""
    text = extract_text_from_pdf(pdf_bytes)
    text_lower = text.lower()

    if company and company in COMPANY_ATS_PROFILES:
        # Single company analysis
        return {
            "mode": "single",
            "analysis": analyze_company_ats(text_lower, company),
        }
    else:
        # Analyze against all companies, rank by pass probability
        results = []
        for comp in COMPANY_ATS_PROFILES:
            r = analyze_company_ats(text_lower, comp)
            if r:
                results.append(r)
        results.sort(key=lambda x: x["pass_probability"], reverse=True)
        return {
            "mode": "all",
            "rankings": [
                {
                    "company": r["company"],
                    "ats_system": r["ats_system"],
                    "pass_probability": r["pass_probability"],
                    "must_have_hit": f"{len(r['must_have_matched'])}/{len(r['must_have_matched'])+len(r['must_have_missing'])}",
                    "tools_hit": f"{len(r['tools_matched'])}/{len(r['tools_matched'])+len(r['tools_missing'])}",
                }
                for r in results
            ],
            "best_match": results[0] if results else None,
            "worst_match": results[-1] if results else None,
        }


# ─── FULL ANALYSIS ──────────────────────────────────────────────────────────

def full_resume_analysis(pdf_bytes: bytes, target_role: str = "VLSI",
                          company: str = None) -> dict:
    """Perform complete resume analysis: ATS score + role match + company bypass."""
    ats = calculate_ats_score(pdf_bytes)
    role = analyze_resume_for_role(pdf_bytes, target_role)
    company_bypass = analyze_company_bypass(pdf_bytes, company)
    return {
        "ats": ats,
        "role_match": role,
        "company_analysis": company_bypass,
    }
