"""Semiconductor Job Classifier — keyword-based + optional AI via OpenRouter."""
import os
import re
import json

# Domain keywords for instant classification (no API needed)
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

FRESHER_KEYWORDS = [
    "fresher", "fresh graduate", "entry level", "entry-level", "0-1 year",
    "0 to 1 year", "0-2 year", "graduate engineer", "junior engineer",
    "campus", "trainee", "intern", "new grad", "recent graduate",
]

EXPERIENCE_PATTERN = re.compile(r"(\d+)\s*[-–to]+\s*(\d+)\s*(?:years?|yrs?)", re.IGNORECASE)


def classify_job(title: str, description: str) -> dict:
    """Classify a job using keyword matching. Returns domain, skills, fresher info."""
    text = f"{title} {description}".lower()
    scores = {}
    matched_skills = []

    for domain, keywords in DOMAIN_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text)
        if count > 0:
            scores[domain] = count
            matched_skills.extend([kw for kw in keywords if kw in text])

    # Best domain
    best_domain = max(scores, key=scores.get) if scores else "General"

    # Fresher detection
    is_fresher = any(kw in text for kw in FRESHER_KEYWORDS)
    exp_match = EXPERIENCE_PATTERN.search(text)
    exp_min = 0
    if exp_match:
        exp_min = int(exp_match.group(1))
        if exp_min <= 1:
            is_fresher = True

    # Salary estimation based on domain and experience
    salary_ranges = {
        "VLSI": (8, 25), "RTL Design": (8, 22), "Physical Design": (8, 22),
        "STA": (8, 20), "DFT": (7, 18), "Verification": (7, 20),
        "FPGA": (6, 18), "Embedded Systems": (5, 15), "Hardware Design": (5, 14),
        "AI Hardware": (10, 30), "Networking Silicon": (8, 22),
        "SoC Architecture": (10, 25), "Analog/Mixed Signal": (8, 22),
        "Processor Design": (10, 28),
    }
    sal = salary_ranges.get(best_domain, (5, 15))

    # Deduplicate skills
    unique_skills = list(set(matched_skills))[:10]

    return {
        "domain": best_domain,
        "skills": unique_skills,
        "experience_min": exp_min,
        "fresher_suitable": is_fresher or exp_min <= 1,
        "salary_estimate_min": sal[0],
        "salary_estimate_max": sal[1],
    }


def classify_with_ai(title: str, description: str) -> dict:
    """Optional: Use OpenRouter (Mistral) for better classification."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return classify_job(title, description)
    try:
        from openai import OpenAI
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        domains = ", ".join(DOMAIN_KEYWORDS.keys())
        prompt = f"""Classify this semiconductor job posting.
Title: {title}
Description: {description[:800]}

Return JSON with: domain (one of: {domains}), skills (list of 5 key skills),
experience_min (integer years), fresher_suitable (boolean), salary_estimate_min (LPA), salary_estimate_max (LPA).
Return ONLY valid JSON, no other text."""

        resp = client.chat.completions.create(
            model="mistralai/mistral-7b-instruct:free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        text = resp.choices[0].message.content.strip()
        # Try to parse JSON from response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            result["ai_classified"] = True
            return result
    except Exception as e:
        print(f"[AI] Classification failed: {e}")
    return classify_job(title, description)


if __name__ == "__main__":
    # Test classifier
    test_title = "VLSI Design Engineer - RTL Design"
    test_desc = "Looking for fresh graduate with knowledge of Verilog, SystemVerilog, ASIC design flow, synthesis, and timing analysis. 0-2 years experience."
    result = classify_job(test_title, test_desc)
    print(f"Title: {test_title}")
    print(f"Result: {json.dumps(result, indent=2)}")
