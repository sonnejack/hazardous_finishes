#!/usr/bin/env python3
"""
Enrich specifications in sft_steps.csv with Type/Class/Grade information.

Reads spec_types.csv and updates sft_steps.csv to replace bare specifications
like "AMS2460" with full versions like "AMS2460 Class 2".
"""

import csv
import sys
from pathlib import Path


def load_spec_types(spec_types_path: str) -> dict[str, str]:
    """
    Load specification types mapping.

    Returns:
        Dictionary mapping base spec -> full spec with type/class/grade
        Only includes specs where type is not "-"
    """
    spec_map = {}

    with open(spec_types_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            spec = row['specification'].strip()
            type_class_grade = row['Type / Class / Grade'].strip()

            if type_class_grade and type_class_grade != '-':
                # Create full specification name
                full_spec = f"{spec} {type_class_grade}"
                spec_map[spec] = full_spec
            else:
                # Keep as-is if no type/class/grade
                spec_map[spec] = spec

    return spec_map


def enrich_specs_in_field(associated_specs: str, spec_map: dict[str, str]) -> str:
    """
    Enrich comma-separated specifications with type/class/grade.

    Args:
        associated_specs: Comma-separated spec codes (e.g., "LMA-PG301,LMA-PJ100,MIL-DTL-5002")
        spec_map: Mapping of base spec -> full spec

    Returns:
        Enriched comma-separated specs (e.g., "LMA-PG301,LMA-PJ100,MIL-DTL-5002")
        or with types if available
    """
    if not associated_specs or not associated_specs.strip():
        return associated_specs

    # Split by comma
    specs = [s.strip() for s in associated_specs.split(',')]

    # Replace each spec with enriched version if available
    enriched_specs = []
    for spec in specs:
        if spec in spec_map:
            enriched_specs.append(spec_map[spec])
        else:
            # Keep original if not in mapping
            enriched_specs.append(spec)

    return ','.join(enriched_specs)


def main():
    # Paths
    spec_types_path = Path("data/inputs/spec_types.csv")
    sft_steps_path = Path("data/inputs/sft_steps.csv")
    backup_path = Path("data/inputs/sft_steps.csv.backup_before_enrichment")

    # Check files exist
    if not spec_types_path.exists():
        print(f"Error: {spec_types_path} not found")
        sys.exit(1)

    if not sft_steps_path.exists():
        print(f"Error: {sft_steps_path} not found")
        sys.exit(1)

    print("Loading specification types...")
    spec_map = load_spec_types(spec_types_path)
    print(f"Loaded {len(spec_map)} specification mappings")

    # Show sample mappings
    print("\nSample enrichments:")
    sample_count = 0
    for base_spec, full_spec in spec_map.items():
        if base_spec != full_spec:
            print(f"  {base_spec} → {full_spec}")
            sample_count += 1
            if sample_count >= 5:
                break

    # Backup original file
    if not backup_path.exists():
        print(f"\nCreating backup: {backup_path}")
        backup_path.write_text(sft_steps_path.read_text(encoding='utf-8-sig'), encoding='utf-8')
    else:
        print(f"\nBackup already exists: {backup_path}")

    # Read sft_steps.csv
    print(f"\nReading {sft_steps_path}...")
    with open(sft_steps_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    print(f"Found {len(rows)} SFT steps")

    # Update associated_specs in each row
    enriched_count = 0
    for row in rows:
        if 'associated_specs' in row and row['associated_specs']:
            original = row['associated_specs']
            enriched = enrich_specs_in_field(original, spec_map)

            if original != enriched:
                row['associated_specs'] = enriched
                enriched_count += 1
                print(f"  {row['sft_code']}: {original} → {enriched}")

    print(f"\nEnriched {enriched_count} SFT steps")

    # Write updated file
    print(f"\nWriting updated {sft_steps_path}...")
    with open(sft_steps_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✓ Successfully enriched specifications in {sft_steps_path}")
    print(f"✓ Original backed up to: {backup_path}")
    print("\nNext step: Re-ingest the data with:")
    print("  hazard-cli ingest")

    return 0


if __name__ == '__main__':
    sys.exit(main())
