"""
Data validation utilities for referential integrity and data quality checks.

Validates database contents after CSV ingestion to ensure:
- Referential integrity (all foreign keys resolve)
- Completeness (required fields populated)
- Format correctness (CAS numbers, JSON, ranges)
"""

import json
import re
import sqlite3
from typing import Any


def validate_referential_integrity(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """
    Validate all foreign key relationships resolve correctly.

    Args:
        conn: SQLite database connection

    Returns:
        List of error dictionaries with keys: type, table, column, issue, details

    Example error:
        {
            "type": "referential_integrity",
            "severity": "error",
            "table": "finish_codes",
            "column": "substrate_id",
            "issue": "orphan_fk",
            "details": "3 rows reference non-existent substrate_id values"
        }
    """
    errors = []
    cursor = conn.cursor()

    # Define FK relationships to check
    fk_checks = [
        ("finish_codes", "substrate_id", "substrates", "id"),
        ("finish_codes", "finish_applied_id", "finish_applied", "id"),
        ("finish_code_steps", "finish_code_id", "finish_codes", "id"),
        ("finish_code_steps", "sft_id", "sft_steps", "id"),
        ("sft_material_links", "sft_id", "sft_steps", "id"),
        ("sft_material_links", "material_id", "materials", "id"),
        ("material_chemicals", "material_id", "materials", "id"),
        ("material_chemicals", "chemical_id", "chemicals", "id"),
        ("spec_dependencies", "spec_material_id", "materials", "id"),
        ("spec_dependencies", "ref_spec_material_id", "materials", "id"),
    ]

    for child_table, child_col, parent_table, parent_col in fk_checks:
        # Check if tables exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (child_table,)
        )
        if not cursor.fetchone():
            continue  # Table doesn't exist yet, skip check

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (parent_table,)
        )
        if not cursor.fetchone():
            errors.append({
                "type": "referential_integrity",
                "severity": "error",
                "table": child_table,
                "column": child_col,
                "issue": "missing_parent_table",
                "details": f"Parent table '{parent_table}' does not exist"
            })
            continue

        # Find orphaned foreign keys
        query = f"""
            SELECT COUNT(*) as orphan_count
            FROM {child_table}
            WHERE {child_col} IS NOT NULL
              AND {child_col} NOT IN (SELECT {parent_col} FROM {parent_table})
        """
        cursor.execute(query)
        result = cursor.fetchone()
        orphan_count = result[0] if result else 0

        if orphan_count > 0:
            errors.append({
                "type": "referential_integrity",
                "severity": "error",
                "table": child_table,
                "column": child_col,
                "issue": "orphan_fk",
                "details": f"{orphan_count} rows reference non-existent {parent_table}.{parent_col} values"
            })

    return errors


def validate_completeness(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """
    Validate required fields are populated (no NULLs where NOT NULL expected).

    Args:
        conn: SQLite database connection

    Returns:
        List of error dictionaries

    Example error:
        {
            "type": "completeness",
            "severity": "error",
            "table": "sft_steps",
            "column": "description",
            "issue": "null_value",
            "details": "2 rows have NULL description"
        }
    """
    errors = []
    cursor = conn.cursor()

    # Define required fields to check (table, column)
    required_fields = [
        ("substrates", "code"),
        ("substrates", "description"),
        ("finish_applied", "code"),
        ("finish_applied", "description"),
        ("finish_codes", "code"),
        ("finish_codes", "substrate_id"),
        ("finish_codes", "finish_applied_id"),
        ("finish_codes", "seq_id"),
        ("sft_steps", "sft_code"),
        ("sft_steps", "description"),
        ("finish_code_steps", "finish_code_id"),
        ("finish_code_steps", "sft_id"),
        ("finish_code_steps", "step_order"),
        ("materials", "base_spec"),
        ("sft_material_links", "sft_id"),
        ("sft_material_links", "material_id"),
        ("chemicals", "name"),
        ("material_chemicals", "material_id"),
        ("material_chemicals", "chemical_id"),
        ("metadata_versions", "source_name"),
        ("metadata_versions", "sha256"),
        ("metadata_versions", "rows_loaded"),
    ]

    for table, column in required_fields:
        # Check if table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        )
        if not cursor.fetchone():
            continue  # Table doesn't exist yet, skip

        query = f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL"
        cursor.execute(query)
        result = cursor.fetchone()
        null_count = result[0] if result else 0

        if null_count > 0:
            errors.append({
                "type": "completeness",
                "severity": "error",
                "table": table,
                "column": column,
                "issue": "null_value",
                "details": f"{null_count} rows have NULL {column}"
            })

    return errors


def validate_formats(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """
    Validate data formats (CAS numbers, JSON strings, numeric ranges).

    Args:
        conn: SQLite database connection

    Returns:
        List of error/warning dictionaries

    Checks:
    - CAS numbers match format: NNNNNN-NN-N or NNNNN-NN-N
    - hazard_flags is valid JSON
    - default_hazard_level is 1-5
    - pct_wt_low <= pct_wt_high
    - Weight percentages are 0-100
    """
    errors = []
    cursor = conn.cursor()

    # Check CAS number format (if chemicals table exists)
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chemicals'"
    )
    if cursor.fetchone():
        # CAS format: NNNNNN-NN-N or NNNNN-NN-N (or NULL)
        cas_pattern = re.compile(r'^\d{4,7}-\d{2}-\d$')

        cursor.execute("SELECT id, name, cas FROM chemicals WHERE cas IS NOT NULL")
        for row in cursor.fetchall():
            chem_id, chem_name, cas = row
            if not cas_pattern.match(cas):
                errors.append({
                    "type": "format",
                    "severity": "warning",
                    "table": "chemicals",
                    "column": "cas",
                    "issue": "invalid_cas_format",
                    "details": f"Chemical '{chem_name}' (id={chem_id}) has invalid CAS: '{cas}'"
                })

        # Check hazard_flags is valid JSON
        cursor.execute("SELECT id, name, hazard_flags FROM chemicals WHERE hazard_flags IS NOT NULL")
        for row in cursor.fetchall():
            chem_id, chem_name, hazard_flags = row
            try:
                json.loads(hazard_flags)
            except json.JSONDecodeError as e:
                errors.append({
                    "type": "format",
                    "severity": "error",
                    "table": "chemicals",
                    "column": "hazard_flags",
                    "issue": "invalid_json",
                    "details": f"Chemical '{chem_name}' (id={chem_id}) has invalid JSON hazard_flags: {e}"
                })

        # Check hazard level range (already enforced by CHECK constraint, but double-check)
        cursor.execute("""
            SELECT id, name, default_hazard_level
            FROM chemicals
            WHERE default_hazard_level IS NOT NULL
              AND (default_hazard_level < 1 OR default_hazard_level > 5)
        """)
        for row in cursor.fetchall():
            chem_id, chem_name, level = row
            errors.append({
                "type": "format",
                "severity": "error",
                "table": "chemicals",
                "column": "default_hazard_level",
                "issue": "out_of_range",
                "details": f"Chemical '{chem_name}' (id={chem_id}) has invalid hazard level: {level} (must be 1-5)"
            })

    # Check material_chemicals weight ranges
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='material_chemicals'"
    )
    if cursor.fetchone():
        # pct_wt_low <= pct_wt_high (CHECK constraint should prevent, but verify)
        cursor.execute("""
            SELECT mc.id, m.base_spec, m.variant, c.name, mc.pct_wt_low, mc.pct_wt_high
            FROM material_chemicals mc
            JOIN materials m ON mc.material_id = m.id
            JOIN chemicals c ON mc.chemical_id = c.id
            WHERE mc.pct_wt_low IS NOT NULL
              AND mc.pct_wt_high IS NOT NULL
              AND mc.pct_wt_low > mc.pct_wt_high
        """)
        for row in cursor.fetchall():
            mc_id, base_spec, variant, chem_name, low, high = row
            variant_str = variant or ""
            errors.append({
                "type": "format",
                "severity": "error",
                "table": "material_chemicals",
                "column": "pct_wt_low, pct_wt_high",
                "issue": "invalid_range",
                "details": f"Material '{base_spec} {variant_str}' - Chemical '{chem_name}': "
                           f"pct_wt_low ({low}) > pct_wt_high ({high})"
            })

        # Warn if total weight exceeds 100% for any material
        cursor.execute("""
            SELECT m.id, m.base_spec, m.variant, SUM(mc.pct_wt_high) as total_max
            FROM materials m
            JOIN material_chemicals mc ON m.id = mc.material_id
            WHERE mc.pct_wt_high IS NOT NULL
            GROUP BY m.id, m.base_spec, m.variant
            HAVING total_max > 100
        """)
        for row in cursor.fetchall():
            mat_id, base_spec, variant, total = row
            variant_str = variant or ""
            errors.append({
                "type": "format",
                "severity": "warning",
                "table": "material_chemicals",
                "column": "pct_wt_high",
                "issue": "exceeds_100_percent",
                "details": f"Material '{base_spec} {variant_str}' has total max weight {total:.1f}% (>100%)"
            })

    # Check finish code composition (code = substrate + finish_applied + seq_id)
    # Note: This validation is optional/informational - finish codes are user-defined
    # and may have custom formatting (e.g., leading zeros in seq_id)
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='finish_codes'"
    )
    if cursor.fetchone():
        cursor.execute("""
            SELECT fc.id, fc.code, s.code, fa.code, fc.seq_id
            FROM finish_codes fc
            JOIN substrates s ON fc.substrate_id = s.id
            JOIN finish_applied fa ON fc.finish_applied_id = fa.id
        """)
        for row in cursor.fetchall():
            fc_id, fc_code, sub_code, fa_code, seq_id = row
            # Format seq_id with leading zeros to match common pattern (2 digits)
            seq_id_str = str(seq_id).zfill(2)
            expected_code = f"{sub_code}{fa_code}{seq_id_str}"

            # Only warn if there's a significant mismatch (not just formatting)
            if fc_code != expected_code:
                # Check if it's just a leading zero issue
                expected_no_zeros = f"{sub_code}{fa_code}{seq_id}"
                if fc_code == expected_no_zeros:
                    # It's fine, just different formatting
                    continue

                errors.append({
                    "type": "format",
                    "severity": "warning",  # Changed to warning since codes are user-defined
                    "table": "finish_codes",
                    "column": "code",
                    "issue": "code_mismatch",
                    "details": f"Finish code '{fc_code}' (id={fc_id}) does not match composition "
                               f"(expected: '{expected_code}')"
                })

    return errors


def generate_validation_report(
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]] = None
) -> dict[str, Any]:
    """
    Generate human-readable validation report.

    Args:
        errors: List of error dictionaries from validation functions
        warnings: Optional list of warning dictionaries

    Returns:
        Dictionary with report structure:
        {
            "status": "pass" | "warnings" | "errors",
            "error_count": int,
            "warning_count": int,
            "errors": [...],
            "warnings": [...],
            "summary": "Human readable summary"
        }
    """
    all_issues = errors or []
    warnings = warnings or []

    # Separate errors and warnings if mixed in errors list
    actual_errors = [e for e in all_issues if e.get("severity") == "error"]
    actual_warnings = [e for e in all_issues if e.get("severity") == "warning"]
    actual_warnings.extend(warnings)

    error_count = len(actual_errors)
    warning_count = len(actual_warnings)

    if error_count > 0:
        status = "errors"
        summary = f"Validation FAILED: {error_count} error(s), {warning_count} warning(s)"
    elif warning_count > 0:
        status = "warnings"
        summary = f"Validation passed with {warning_count} warning(s)"
    else:
        status = "pass"
        summary = "Validation passed: no errors or warnings"

    return {
        "status": status,
        "error_count": error_count,
        "warning_count": warning_count,
        "errors": actual_errors,
        "warnings": actual_warnings,
        "summary": summary
    }


def validate_all(conn: sqlite3.Connection) -> dict[str, Any]:
    """
    Run all validation checks and return comprehensive report.

    Args:
        conn: SQLite database connection

    Returns:
        Validation report dictionary from generate_validation_report()

    Example:
        >>> conn = sqlite3.connect("db/engine.sqlite")
        >>> report = validate_all(conn)
        >>> print(report["summary"])
        Validation passed: no errors or warnings
    """
    all_issues = []

    # Run all validators
    all_issues.extend(validate_referential_integrity(conn))
    all_issues.extend(validate_completeness(conn))
    all_issues.extend(validate_formats(conn))

    return generate_validation_report(all_issues)
