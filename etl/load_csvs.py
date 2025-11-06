"""
CSV ingestion orchestrator for hazardous finishes database.

Loads CSV files from data/inputs/ into SQLite database with:
- Deterministic upsert logic (no duplicates by code keys)
- SHA256 tracking in metadata_versions table
- Row count recording
- Validation report generation
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from .hashing import compute_sha256
from .validators import validate_all


def initialize_database(db_path: str, schema_path: str = "db/schema.sql") -> sqlite3.Connection:
    """
    Initialize SQLite database with schema if not exists.

    Args:
        db_path: Path to SQLite database file
        schema_path: Path to schema.sql file

    Returns:
        SQLite connection with foreign keys enabled

    Raises:
        FileNotFoundError: If schema file not found
        sqlite3.Error: If database creation fails
    """
    schema_file = Path(schema_path)
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # Execute schema DDL
    with open(schema_file, "r") as f:
        schema_sql = f.read()
        conn.executescript(schema_sql)

    conn.commit()
    return conn


def record_metadata(
    conn: sqlite3.Connection,
    source_name: str,
    sha256: str,
    rows_loaded: int
) -> None:
    """
    Record CSV ingestion metadata for lineage tracking.

    Args:
        conn: SQLite connection
        source_name: CSV filename (e.g., "substrates.csv")
        sha256: SHA256 hash of file
        rows_loaded: Number of rows successfully loaded

    Raises:
        sqlite3.Error: If insert fails
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO metadata_versions (source_name, sha256, rows_loaded, loaded_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(source_name) DO UPDATE SET
            sha256 = excluded.sha256,
            rows_loaded = excluded.rows_loaded,
            loaded_at = excluded.loaded_at
    """, (source_name, sha256, rows_loaded, datetime.now().isoformat()))
    conn.commit()


def load_substrates(csv_path: str, conn: sqlite3.Connection) -> int:
    """
    Load substrates from CSV.

    CSV columns: code, description, source_doc?, program?

    Args:
        csv_path: Path to substrates.csv
        conn: SQLite connection

    Returns:
        Number of rows loaded

    Raises:
        FileNotFoundError: If CSV not found
        pd.errors.EmptyDataError: If CSV is empty
        sqlite3.Error: If insert fails
    """
    df = pd.read_csv(csv_path, dtype=str)
    df = df.fillna("")  # Convert NaN to empty string

    required_cols = ["code", "description"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in {csv_path}: {missing_cols}")

    cursor = conn.cursor()
    for _, row in df.iterrows():
        source_doc = row.get("source_doc", "").strip() if "source_doc" in df.columns else ""
        program = row.get("program", "").strip() if "program" in df.columns else ""

        cursor.execute("""
            INSERT INTO substrates (code, description, source_doc, program)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(code, program) DO UPDATE SET
                description = excluded.description,
                source_doc = excluded.source_doc
        """, (row["code"].strip(), row["description"].strip(), source_doc, program))

    conn.commit()
    return len(df)


def load_finish_applied(csv_path: str, conn: sqlite3.Connection) -> int:
    """
    Load finish_applied from CSV.

    CSV columns: code, description, source_doc?, program?, associated_specs?

    Args:
        csv_path: Path to finish_applied.csv
        conn: SQLite connection

    Returns:
        Number of rows loaded
    """
    df = pd.read_csv(csv_path, dtype=str)
    df = df.fillna("")

    required_cols = ["code", "description"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in {csv_path}: {missing_cols}")

    cursor = conn.cursor()
    for _, row in df.iterrows():
        source_doc = row.get("source_doc", "").strip() if "source_doc" in df.columns else ""
        program = row.get("program", "").strip() if "program" in df.columns else ""
        associated_specs = row.get("associated_specs", "").strip() if "associated_specs" in df.columns else ""

        cursor.execute("""
            INSERT INTO finish_applied (code, description, source_doc, program, associated_specs)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code, program) DO UPDATE SET
                description = excluded.description,
                source_doc = excluded.source_doc,
                associated_specs = excluded.associated_specs
        """, (row["code"].strip(), row["description"].strip(), source_doc, program, associated_specs))

    conn.commit()
    return len(df)


def load_finish_codes(csv_path: str, conn: sqlite3.Connection) -> int:
    """
    Load finish_codes from CSV.

    CSV columns: finish_code, substrate_code, finish_applied_code, seq_id,
                 (description|finish_code_description)?, notes?, sft_steps?

    The sft_steps column (if present) should contain JSON arrays like:
        [SFT0001, SFT0002, ...]
    These will be automatically parsed and loaded into finish_code_steps table.

    Args:
        csv_path: Path to finish_codes.csv
        conn: SQLite connection

    Returns:
        Number of rows loaded
    """
    # Use error_bad_lines=False to skip malformed rows (deprecated, using on_bad_lines)
    try:
        df = pd.read_csv(csv_path, dtype={"seq_id": str}, on_bad_lines='warn', encoding='utf-8-sig')
    except TypeError:
        # Fallback for older pandas versions
        df = pd.read_csv(csv_path, dtype={"seq_id": str}, encoding='utf-8-sig')

    df = df.fillna("")

    required_cols = ["finish_code", "substrate_code", "finish_applied_code", "seq_id"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in {csv_path}: {missing_cols}")

    cursor = conn.cursor()
    sft_steps_data = []  # Store SFT step mappings for later processing

    for _, row in df.iterrows():
        # Get program from row
        program = row.get("program", "").strip() if "program" in df.columns else ""

        # Lookup substrate_id by (code, program)
        cursor.execute("SELECT id FROM substrates WHERE code = ? AND program = ?",
                      (row["substrate_code"].strip(), program))
        substrate_result = cursor.fetchone()
        if not substrate_result:
            raise ValueError(
                f"Substrate code '{row['substrate_code']}' for program '{program}' not found for finish_code '{row['finish_code']}'"
            )
        substrate_id = substrate_result[0]

        # Lookup finish_applied_id by (code, program)
        cursor.execute("SELECT id FROM finish_applied WHERE code = ? AND program = ?",
                      (row["finish_applied_code"].strip(), program))
        fa_result = cursor.fetchone()
        if not fa_result:
            raise ValueError(
                f"Finish applied code '{row['finish_applied_code']}' for program '{program}' not found for finish_code '{row['finish_code']}'"
            )
        fa_id = fa_result[0]

        # Handle description - support both 'description' and 'finish_code_description'
        description = ""
        if "description" in df.columns:
            description = row.get("description", "").strip()
        elif "finish_code_description" in df.columns:
            description = row.get("finish_code_description", "").strip()

        notes = row.get("notes", "").strip() if "notes" in df.columns else ""
        source_doc = row.get("source_doc", "").strip() if "source_doc" in df.columns else ""
        # program already extracted at line 204
        associated_specs = row.get("associated_specs", "").strip() if "associated_specs" in df.columns else ""

        # Convert seq_id to int, stripping any whitespace
        seq_id = str(row["seq_id"]).strip()
        if not seq_id.isdigit():
            seq_id = "0"
        seq_id = int(seq_id)

        cursor.execute("""
            INSERT INTO finish_codes (code, substrate_id, finish_applied_id, seq_id, description, notes, source_doc, program, associated_specs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code, program) DO UPDATE SET
                substrate_id = excluded.substrate_id,
                finish_applied_id = excluded.finish_applied_id,
                seq_id = excluded.seq_id,
                description = excluded.description,
                notes = excluded.notes,
                source_doc = excluded.source_doc,
                associated_specs = excluded.associated_specs
        """, (row["finish_code"].strip(), substrate_id, fa_id, seq_id, description, notes, source_doc, program, associated_specs))

        # Parse sft_steps if present
        if "sft_steps" in df.columns and row["sft_steps"]:
            sft_steps_str = str(row["sft_steps"]).strip()
            if sft_steps_str and sft_steps_str != "[]":
                sft_steps_data.append((row["finish_code"].strip(), sft_steps_str))

    conn.commit()

    # Now process sft_steps mappings
    if sft_steps_data:
        _load_sft_steps_from_embedded_array(sft_steps_data, conn)

    return len(df)


def _load_sft_steps_from_embedded_array(sft_steps_data: list[tuple[str, str]], conn: sqlite3.Connection):
    """
    Parse embedded SFT steps arrays and load into finish_code_steps table.

    Args:
        sft_steps_data: List of (finish_code, sft_steps_json_string) tuples
        conn: SQLite connection
    """
    import json
    import re

    cursor = conn.cursor()

    for finish_code, sft_steps_str in sft_steps_data:
        # Parse the array - handle both proper JSON and Python-style arrays
        # Clean up the string: remove brackets, split by comma
        sft_steps_str = sft_steps_str.strip()

        # Try JSON parsing first
        sft_codes = []
        try:
            sft_codes = json.loads(sft_steps_str)
        except json.JSONDecodeError:
            # Fallback: manual parsing
            # Remove brackets and quotes, split by comma
            clean_str = re.sub(r'[\[\]\"\']', '', sft_steps_str)
            sft_codes = [code.strip() for code in clean_str.split(',') if code.strip()]

        if not sft_codes:
            continue

        # Get finish_code_id
        cursor.execute("SELECT id FROM finish_codes WHERE code = ?", (finish_code,))
        fc_result = cursor.fetchone()
        if not fc_result:
            continue  # Skip if finish code not found
        fc_id = fc_result[0]

        # Insert each SFT step with order
        for step_order, sft_code in enumerate(sft_codes, start=1):
            sft_code = str(sft_code).strip()
            if not sft_code:
                continue

            # Lookup SFT step ID
            cursor.execute("SELECT id FROM sft_steps WHERE sft_code = ?", (sft_code,))
            sft_result = cursor.fetchone()
            if not sft_result:
                print(f"Warning: SFT code '{sft_code}' not found for finish_code '{finish_code}' - skipping")
                continue
            sft_id = sft_result[0]

            # Insert the mapping
            cursor.execute("""
                INSERT INTO finish_code_steps (finish_code_id, sft_id, step_order)
                VALUES (?, ?, ?)
                ON CONFLICT(finish_code_id, sft_id) DO UPDATE SET
                    step_order = excluded.step_order
            """, (fc_id, sft_id, step_order))

    conn.commit()


def load_sft_steps(csv_path: str, conn: sqlite3.Connection) -> int:
    """
    Load sft_steps from CSV.

    CSV columns: sft_code, parent_group?, description, associated_specs?, source_doc?, last_review?, notes?

    Args:
        csv_path: Path to sft_steps.csv
        conn: SQLite connection

    Returns:
        Number of rows loaded
    """
    df = pd.read_csv(csv_path, dtype=str)
    df = df.fillna("")

    required_cols = ["sft_code", "description"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in {csv_path}: {missing_cols}")

    cursor = conn.cursor()
    for _, row in df.iterrows():
        parent_group = row.get("parent_group", "").strip() if "parent_group" in df.columns else None
        associated_specs = row.get("associated_specs", "").strip() if "associated_specs" in df.columns else None
        source_doc = row.get("source_doc", "").strip() if "source_doc" in df.columns else None
        last_review = row.get("last_review", "").strip() if "last_review" in df.columns else None
        notes = row.get("notes", "").strip() if "notes" in df.columns else None

        cursor.execute("""
            INSERT INTO sft_steps (sft_code, parent_group, description, associated_specs, source_doc, last_review, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sft_code) DO UPDATE SET
                parent_group = excluded.parent_group,
                description = excluded.description,
                associated_specs = excluded.associated_specs,
                source_doc = excluded.source_doc,
                last_review = excluded.last_review,
                notes = excluded.notes
        """, (
            row["sft_code"].strip(),
            parent_group or None,
            row["description"].strip(),
            associated_specs or None,
            source_doc or None,
            last_review or None,
            notes or None
        ))

    conn.commit()
    return len(df)


def load_finish_code_steps(csv_path: str, conn: sqlite3.Connection) -> int:
    """
    Load finish_code_steps from CSV.

    CSV columns: finish_code, sft_code, step_order

    Args:
        csv_path: Path to finish_code_steps.csv
        conn: SQLite connection

    Returns:
        Number of rows loaded
    """
    df = pd.read_csv(csv_path, dtype={"step_order": int})
    df = df.fillna("")

    required_cols = ["finish_code", "sft_code", "step_order"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in {csv_path}: {missing_cols}")

    cursor = conn.cursor()
    for _, row in df.iterrows():
        # Lookup finish_code_id
        cursor.execute("SELECT id FROM finish_codes WHERE code = ?", (row["finish_code"].strip(),))
        fc_result = cursor.fetchone()
        if not fc_result:
            raise ValueError(f"Finish code '{row['finish_code']}' not found")
        fc_id = fc_result[0]

        # Lookup sft_id
        cursor.execute("SELECT id FROM sft_steps WHERE sft_code = ?", (row["sft_code"].strip(),))
        sft_result = cursor.fetchone()
        if not sft_result:
            raise ValueError(f"SFT code '{row['sft_code']}' not found")
        sft_id = sft_result[0]

        cursor.execute("""
            INSERT INTO finish_code_steps (finish_code_id, sft_id, step_order)
            VALUES (?, ?, ?)
            ON CONFLICT(finish_code_id, sft_id) DO UPDATE SET
                step_order = excluded.step_order
        """, (fc_id, sft_id, int(row["step_order"])))

    conn.commit()
    return len(df)


def load_materials(csv_path: str, conn: sqlite3.Connection) -> int:
    """
    Load materials from CSV.

    CSV columns: base_spec, variant?, description?, notes?

    Args:
        csv_path: Path to materials_map.csv
        conn: SQLite connection

    Returns:
        Number of rows loaded
    """
    df = pd.read_csv(csv_path, dtype=str)
    df = df.fillna("")

    required_cols = ["base_spec"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in {csv_path}: {missing_cols}")

    cursor = conn.cursor()
    for _, row in df.iterrows():
        variant = row.get("variant", "").strip() if "variant" in df.columns else ""
        variant = variant if variant else None  # Convert empty string to NULL

        description = row.get("description", "").strip() if "description" in df.columns else ""
        notes = row.get("notes", "").strip() if "notes" in df.columns else ""

        cursor.execute("""
            INSERT INTO materials (base_spec, variant, description, notes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(base_spec, variant) DO UPDATE SET
                description = excluded.description,
                notes = excluded.notes
        """, (row["base_spec"].strip(), variant, description, notes))

    conn.commit()
    return len(df)


def load_sft_material_links(csv_path: str, conn: sqlite3.Connection) -> int:
    """
    Load sft_material_links from CSV.

    CSV columns: sft_code, base_spec, variant?, note?

    Args:
        csv_path: Path to sft_material_links.csv
        conn: SQLite connection

    Returns:
        Number of rows loaded
    """
    df = pd.read_csv(csv_path, dtype=str)
    df = df.fillna("")

    required_cols = ["sft_code", "base_spec"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in {csv_path}: {missing_cols}")

    cursor = conn.cursor()
    for _, row in df.iterrows():
        # Lookup sft_id
        cursor.execute("SELECT id FROM sft_steps WHERE sft_code = ?", (row["sft_code"].strip(),))
        sft_result = cursor.fetchone()
        if not sft_result:
            raise ValueError(f"SFT code '{row['sft_code']}' not found")
        sft_id = sft_result[0]

        # Lookup material_id
        variant = row.get("variant", "").strip() if "variant" in df.columns else ""
        variant = variant if variant else None

        cursor.execute(
            "SELECT id FROM materials WHERE base_spec = ? AND (variant = ? OR (variant IS NULL AND ? IS NULL))",
            (row["base_spec"].strip(), variant, variant)
        )
        mat_result = cursor.fetchone()
        if not mat_result:
            raise ValueError(
                f"Material '{row['base_spec']} {variant or ''}' not found for SFT '{row['sft_code']}'"
            )

        mat_id = mat_result[0]

        note = row.get("note", "").strip() if "note" in df.columns else ""

        cursor.execute("""
            INSERT INTO sft_material_links (sft_id, material_id, note)
            VALUES (?, ?, ?)
        """, (sft_id, mat_id, note or None))

    conn.commit()
    return len(df)


def load_chemicals(csv_path: str, conn: sqlite3.Connection) -> int:
    """
    Load chemicals from CSV.

    CSV columns: name, cas, hazard_flags, default_hazard_level

    Args:
        csv_path: Path to chemicals.csv
        conn: SQLite connection

    Returns:
        Number of rows loaded
    """
    df = pd.read_csv(csv_path, dtype={"default_hazard_level": "Int64"})  # Nullable int
    df = df.fillna("")

    required_cols = ["name"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in {csv_path}: {missing_cols}")

    cursor = conn.cursor()
    for _, row in df.iterrows():
        cas = row.get("cas", "").strip() if "cas" in df.columns else ""
        cas = cas if cas else None

        hazard_flags = row.get("hazard_flags", "").strip() if "hazard_flags" in df.columns else ""
        hazard_flags = hazard_flags if hazard_flags else None

        # Validate JSON if present
        if hazard_flags:
            try:
                json.loads(hazard_flags)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in hazard_flags for chemical '{row['name']}': {e}")

        hazard_level = row.get("default_hazard_level") if "default_hazard_level" in df.columns else None
        if pd.notna(hazard_level):
            hazard_level = int(hazard_level)
        else:
            hazard_level = None

        cursor.execute("""
            INSERT INTO chemicals (name, cas, hazard_flags, default_hazard_level)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cas) DO UPDATE SET
                name = excluded.name,
                hazard_flags = excluded.hazard_flags,
                default_hazard_level = excluded.default_hazard_level
        """, (row["name"].strip(), cas, hazard_flags, hazard_level))

    conn.commit()
    return len(df)


def load_material_chemicals(csv_path: str, conn: sqlite3.Connection) -> int:
    """
    Load material_chemicals from CSV.

    CSV columns: base_spec, variant?, chemical_name, cas, pct_wt_low, pct_wt_high, notes?

    Args:
        csv_path: Path to material_chemicals.csv
        conn: SQLite connection

    Returns:
        Number of rows loaded
    """
    df = pd.read_csv(csv_path, dtype={"pct_wt_low": float, "pct_wt_high": float})
    df = df.fillna("")

    required_cols = ["base_spec", "cas"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in {csv_path}: {missing_cols}")

    cursor = conn.cursor()
    for _, row in df.iterrows():
        # Lookup material_id
        variant = row.get("variant", "").strip() if "variant" in df.columns else ""
        variant = variant if variant else None

        cursor.execute(
            "SELECT id FROM materials WHERE base_spec = ? AND (variant = ? OR (variant IS NULL AND ? IS NULL))",
            (row["base_spec"].strip(), variant, variant)
        )
        mat_result = cursor.fetchone()
        if not mat_result:
            raise ValueError(f"Material '{row['base_spec']} {variant or ''}' not found")
        mat_id = mat_result[0]

        # Lookup chemical_id by CAS
        cursor.execute("SELECT id FROM chemicals WHERE cas = ?", (row["cas"].strip(),))
        chem_result = cursor.fetchone()
        if not chem_result:
            raise ValueError(f"Chemical with CAS '{row['cas']}' not found")
        chem_id = chem_result[0]

        pct_low = row.get("pct_wt_low") if "pct_wt_low" in df.columns else None
        pct_low = float(pct_low) if pd.notna(pct_low) else None

        pct_high = row.get("pct_wt_high") if "pct_wt_high" in df.columns else None
        pct_high = float(pct_high) if pd.notna(pct_high) else None

        notes = row.get("notes", "").strip() if "notes" in df.columns else ""

        cursor.execute("""
            INSERT INTO material_chemicals (material_id, chemical_id, pct_wt_low, pct_wt_high, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (mat_id, chem_id, pct_low, pct_high, notes or None))

    conn.commit()
    return len(df)


def ingest_all(input_dir: str, db_path: str, schema_path: str = "db/schema.sql") -> dict[str, Any]:
    """
    Orchestrate full CSV ingestion into SQLite database.

    Load order ensures parent tables loaded before child tables.

    Args:
        input_dir: Directory containing CSV files
        db_path: Path to SQLite database
        schema_path: Path to schema.sql file

    Returns:
        Ingestion report dictionary with:
        - status: "success" | "partial" | "failed"
        - loaded_files: {filename: {rows: int, sha256: str}}
        - validation_report: {...}
        - errors: [...]

    Raises:
        FileNotFoundError: If input_dir or required CSV not found
        ValueError: If CSV validation fails
        sqlite3.Error: If database operations fail
    """
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    # Initialize database
    conn = initialize_database(db_path, schema_path)

    loaded_files = {}
    errors = []

    # Define load order (parent tables first)
    load_sequence = [
        ("substrates.csv", load_substrates),
        ("finish_applied.csv", load_finish_applied),
        ("finish_codes.csv", load_finish_codes),
        ("sft_steps.csv", load_sft_steps),
        ("finish_code_steps.csv", load_finish_code_steps),
        ("materials_map.csv", load_materials),
        ("chemicals.csv", load_chemicals),
        ("sft_material_links.csv", load_sft_material_links),
        ("material_chemicals.csv", load_material_chemicals),
    ]

    for filename, load_func in load_sequence:
        csv_path = input_path / filename
        if not csv_path.exists():
            errors.append({
                "file": filename,
                "error": "File not found",
                "severity": "error"
            })
            continue

        try:
            # Compute SHA256
            sha256 = compute_sha256(csv_path)

            # Load CSV
            rows_loaded = load_func(str(csv_path), conn)

            # Record metadata
            record_metadata(conn, filename, sha256, rows_loaded)

            loaded_files[filename] = {
                "rows": rows_loaded,
                "sha256": sha256
            }

        except Exception as e:
            errors.append({
                "file": filename,
                "error": str(e),
                "severity": "error"
            })

    # Run validation
    validation_report = validate_all(conn)

    conn.close()

    # Determine overall status
    if errors:
        status = "failed" if len(errors) == len(load_sequence) else "partial"
    elif validation_report["status"] == "errors":
        status = "failed"
    elif validation_report["status"] == "warnings":
        status = "success_with_warnings"
    else:
        status = "success"

    return {
        "status": status,
        "loaded_files": loaded_files,
        "validation_report": validation_report,
        "errors": errors,
        "timestamp": datetime.now().isoformat()
    }
