#!/usr/bin/env python3
"""
Fix malformed rows in finish_codes.csv by manually patching known problematic lines.
"""

import sys
from pathlib import Path


def main():
    input_file = Path("data/inputs/finish_codes.csv")
    backup_file = Path("data/inputs/finish_codes.csv.backup")

    if not input_file.exists():
        print(f"Error: {input_file} not found")
        sys.exit(1)

    # Backup original (if not already backed up)
    if not backup_file.exists():
        print(f"Creating backup: {backup_file}")
        backup_file.write_text(input_file.read_text(encoding='utf-8-sig'))
    else:
        print(f"Backup already exists: {backup_file}")

    # Read lines
    lines = input_file.read_text(encoding='utf-8-sig').splitlines()
    fixed_count = 0

    # Fix known problematic lines
    # These are zero-indexed (line 161 in file = index 160)
    fixes = {
        160: 'FW07,F,W,07,"WHITE TOPCOAT ALL SURFACES PRIMER ZINC NICKEL PLATING","[SFT0001, SFT0102, SFT0309, SFT0403, SFT0501, SFT0901]"',
        161: 'LB01,L,B,01,"PASSIVATE CRES TUBING- ALL SURFACES","[SFT0107]"',
        164: 'LA01,L,A,01,"ALUMINUM 5000/6000 TUBING ANODIZE ALL SURFACES","[SFT0106, SFT0209, SFT0901]"',
    }

    for idx, fixed_line in fixes.items():
        if idx < len(lines):
            old_line = lines[idx]
            lines[idx] = fixed_line
            print(f"Fixed line {idx + 1}:")
            print(f"  OLD: {old_line[:80]}...")
            print(f"  NEW: {fixed_line[:80]}...")
            fixed_count += 1

    # Check for other lines that might have issues (lines with unmatched quotes)
    for i, line in enumerate(lines[1:], start=2):  # Skip header
        # Quick heuristic: count quotes, should be even
        if line.count('"') % 2 != 0:
            print(f"Warning: Line {i} has unmatched quotes: {line[:80]}...")

    # Write fixed file
    output = '\n'.join(lines) + '\n'
    input_file.write_text(output, encoding='utf-8')

    print(f"\nFixed {fixed_count} known problematic lines")
    print(f"Fixed file written to: {input_file}")

    # Verify with pandas
    try:
        import pandas as pd
        df = pd.read_csv(input_file, dtype={'seq_id': str}, encoding='utf-8-sig')
        print(f"\n✓ Verification: Successfully loaded {len(df)} rows (should be 258)")
        return 0
    except Exception as e:
        print(f"\n✗ Verification failed: {e}")
        print("There may be additional malformed rows to fix")
        return 1


if __name__ == '__main__':
    sys.exit(main())
