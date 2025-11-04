import re
import pandas as pd
from pathlib import Path

# ----------------------------
# SFT Specification Extractor
# ----------------------------
# Reads data/inputs/sft_steps.csv
# Adds/overwrites associated_specs column
# Writes data/inputs/sft_steps_with_specs.csv
# ----------------------------

# Expandable prefixes
PREFIX = r"(?:MIL|AMS|ASTM|LMA|QQ|SAE|ISO|IEC|NAVAIR|NAVSEA|NAS|MS|AN|BAC|FED-STD)"

# Common trailing words to stop extraction
STOP_WORDS = {
    "IAW", "PER", "CLASS", "TYPE", "GRADE", "COLOR", "COAT", "PRIME", "ANODIZE", "SURFACE",
    "SURFACES", "SEAL", "UNSEALED", "SEALED", "DYE", "BLACK", "GRAY", "WHITE", "OR", "AND",
    "THEN", "WITH", "TO", "FOR", "ON", "IN", "AT", "IF", "WHERE", "SPECIFIED", "WHERESPECIFIED",
    "AS", "INCLUDES", "COMPATIBLE", "ADDITIONAL", "NOTES", "FINISH", "TOPCOAT", "FLAT", "GLOSS",
    "SEMI", "MATTE", "DARK", "GREEN", "RED", "YELLOW", "MEDIUM", "LIGHT", "CAMOUFLAGE", "HAZE",
    "PTFELINER", "CORROSIONPREVENTIVECOMPOUND", "GENERAL", "PURPOSE", "SOLVENT"
}

END_PUNCT = set(",.;:)")

# Capture bare P##### specs (e.g., P57004, P55002)
P_SPEC = re.compile(r"\bP\d{4,6}\b", re.IGNORECASE)

def extract_specs(text: str) -> list[str]:
    """Extracts specification identifiers from an SFT description."""
    if not isinstance(text, str) or not text.strip():
        return []

    specs: list[str] = []

    # Temporarily replace "IAW", "OR", and "AND" to avoid interfering with regex
    text = re.sub(r"\b(IAW|OR|AND)\b", lambda x: f"___{x.group(0)}___", text)

    # Pass 1: standalone P##### specs
    for m in P_SPEC.finditer(text):
        specs.append(m.group(0).upper())

    # Pass 2: prefixed specs (MIL-DTL-5002, AMS-QQ-P-416, LMA-MN040, etc.)
    for m in re.finditer(rf"\b{PREFIX}\b[-\s]*([A-Za-z0-9-]*)", text, re.IGNORECASE):
        if not m.group(0).endswith(("_", "-")):
            specs.append(m.group(0).upper().strip())

    # Restore temporarily replaced words
    text = re.sub(r"___(IAW|OR|AND)___", lambda x: x.group(1), text)

    # Deduplicate while preserving order and remove all spaces but keep dashes
    seen = set()
    ordered = []
    for s in specs:
        cleaned_spec = re.sub(r"\s+", "", s)
        if cleaned_spec not in seen:
            seen.add(cleaned_spec)
            ordered.append(cleaned_spec)
    return ordered


def main():
    input_path = Path("data/inputs/sft_steps.csv")
    output_path = Path("data/inputs/sft_steps_with_specs.csv")

    if not input_path.exists():
        print(f"❌ Input file not found: {input_path}")
        return

    df = pd.read_csv(input_path)
    if "description" not in df.columns:
        print("❌ Column 'description' not found in CSV.")
        return

    df["associated_specs"] = df["description"].apply(
        lambda x: ",".join(extract_specs(x))
    )
    df.to_csv(output_path, index=False)
    print(f"✅ Extracted specifications written to {output_path}")


if __name__ == "__main__":
    main()
