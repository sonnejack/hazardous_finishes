import re
import csv
import json
from pathlib import Path

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------
INPUT_FILE = Path("data/inputs/LMA-PJ100.rtf")
OUTPUT_FILE = Path("data/inputs/finish_codes_flat.csv")

# Match finish codes: 0000 or 1–2 letters + 2 digits
FINISH_CODE_RE = re.compile(r"(?<!\S)(?:([A-Z]{1,2}\d{2})|(0000))(?!\S)")
SFT_RE = re.compile(r"\bSFT\d{4}\b", re.IGNORECASE)

# ---------------------------------------------------------------------
# CLEANUP
# ---------------------------------------------------------------------
def clean_rtf(raw: str) -> str:
    """Remove RTF control codes and normalize whitespace."""
    s = re.sub(r"\\'[0-9a-fA-F]{2}", " ", raw)
    s = re.sub(r"\\[a-zA-Z]+-?\d*(?:\s|)", " ", s)
    s = s.replace("{", " ").replace("}", " ").replace("\\", " ")
    s = re.sub(r"\s+", " ", s)
    return s.upper().strip()

# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------
def find_codes(text: str):
    return list(FINISH_CODE_RE.finditer(text))

def split_code_parts(code: str):
    if code == "0000":
        return "0", "0", "00"
    letters = "".join(ch for ch in code if ch.isalpha())
    digits = "".join(ch for ch in code if ch.isdigit())
    if len(letters) == 2:
        s, f = letters[0], letters[1]
    else:
        s, f = letters[0], "0"
    return s, f, digits[-2:]

# ---------------------------------------------------------------------
# MAIN EXTRACTION
# ---------------------------------------------------------------------
def extract_finish_codes(text: str):
    matches = find_codes(text)
    results = []

    for i, m in enumerate(matches):
        code = m.group(1) or m.group(2)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()

        # description = text before first SFT####
        first_sft = SFT_RE.search(block)
        desc = block[: first_sft.start()].strip() if first_sft else block
        desc = re.sub(r"\s+", " ", desc)

        # collect SFT steps
        sft_list = SFT_RE.findall(block)
        s, f, seq = split_code_parts(code)

        results.append({
            "finish_code": code,
            "substrate_code": s,
            "finish_applied_code": f,
            "seq_id": seq,
            "finish_code_description": desc,
            "sft_steps": json.dumps(sorted(set(sft_list)))
        })

    return results

# ---------------------------------------------------------------------
# RUNNER
# ---------------------------------------------------------------------
def main():
    if not INPUT_FILE.exists():
        print(f"❌ Missing file: {INPUT_FILE}")
        return

    raw = INPUT_FILE.read_text(errors="ignore")
    text = clean_rtf(raw)
    rows = extract_finish_codes(text)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "finish_code",
                "substrate_code",
                "finish_applied_code",
                "seq_id",
                "finish_code_description",
                "sft_steps",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Extracted {len(rows)} finish codes → {OUTPUT_FILE}")

# ---------------------------------------------------------------------
if __name__ == "__main__":
    main()
