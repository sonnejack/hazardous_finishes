"""
Query engine for retrieving finish code hierarchies with full traceability.

Provides functions to:
- Retrieve complete finish code trees (substrate → finish → steps → materials → chemicals)
- Include provenance data (CSV SHAs, load timestamps)
- Return structured JSON for CLI and GUI consumption
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


def get_finish_code_tree(finish_code: str, db_path: str = "data/hazardous_finishes.sqlite") -> dict[str, Any]:
    """
    Retrieve complete finish code hierarchy with all related data.

    Args:
        finish_code: Finish code to query (e.g., "BP27")
        db_path: Path to SQLite database

    Returns:
        Dictionary with structure:
        {
            "finish_code": str,
            "parsed": {
                "substrate": {"code": str, "description": str},
                "finish_applied": {"code": str, "description": str},
                "seq_id": int,
                "finish_description": str | null
            },
            "steps": [
                {
                    "sft_code": str,
                    "step_order": int,
                    "parent_group": str | null,
                    "description": str,
                    "associated_specs": str | null,
                    "source_doc": str | null,
                    "last_review": str | null,
                    "notes": str | null,
                    "materials": [
                        {
                            "base_spec": str,
                            "variant": str | null,
                            "description": str | null,
                            "chemicals": [
                                {
                                    "name": str,
                                    "cas": str | null,
                                    "pct_wt_low": float | null,
                                    "pct_wt_high": float | null,
                                    "hazard_flags": dict | null,
                                    "default_hazard_level": int | null
                                }
                            ]
                        }
                    ]
                }
            ],
            "provenance": {
                "csv_shas": {filename: sha256, ...},
                "loaded_at": str (ISO datetime of most recent load)
            }
        }

        If finish_code not found, returns:
        {
            "error": "Finish code not found",
            "finish_code": str,
            "available_codes": [list of valid codes]
        }

    Raises:
        FileNotFoundError: If database file not found
        sqlite3.Error: If database query fails
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    cursor = conn.cursor()

    # Check if finish code exists
    cursor.execute("SELECT * FROM finish_codes WHERE code = ?", (finish_code,))
    fc_row = cursor.fetchone()

    if not fc_row:
        # Return error with available codes
        cursor.execute("SELECT code FROM finish_codes ORDER BY code LIMIT 10")
        available = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {
            "error": "Finish code not found",
            "finish_code": finish_code,
            "available_codes": available
        }

    # Get parsed components
    cursor.execute("""
        SELECT
            fc.code,
            fc.seq_id,
            fc.description AS finish_description,
            fc.notes,
            fc.source_doc,
            fc.program,
            fc.associated_specs,
            s.code AS substrate_code,
            s.description AS substrate_description,
            fa.code AS finish_applied_code,
            fa.description AS finish_applied_description,
            fa.associated_specs AS finish_applied_specs
        FROM finish_codes fc
        JOIN substrates s ON fc.substrate_id = s.id
        JOIN finish_applied fa ON fc.finish_applied_id = fa.id
        WHERE fc.code = ?
    """, (finish_code,))
    parsed_row = cursor.fetchone()

    parsed = {
        "substrate": {
            "code": parsed_row["substrate_code"],
            "description": parsed_row["substrate_description"]
        },
        "finish_applied": {
            "code": parsed_row["finish_applied_code"],
            "description": parsed_row["finish_applied_description"]
        },
        "seq_id": parsed_row["seq_id"],
        "finish_description": parsed_row["finish_description"],
        "notes": parsed_row["notes"],
        "source_doc": parsed_row["source_doc"],
        "program": parsed_row["program"],
        "associated_specs": parsed_row["associated_specs"]
    }

    # Get ordered SFT steps
    cursor.execute("""
        SELECT
            sft.sft_code,
            sft.parent_group,
            sft.description,
            sft.associated_specs,
            sft.source_doc,
            sft.last_review,
            sft.notes,
            fcs.step_order
        FROM finish_code_steps fcs
        JOIN sft_steps sft ON fcs.sft_id = sft.id
        WHERE fcs.finish_code_id = (SELECT id FROM finish_codes WHERE code = ?)
        ORDER BY fcs.step_order
    """, (finish_code,))
    sft_rows = cursor.fetchall()

    steps = []
    for sft_row in sft_rows:
        sft_code = sft_row["sft_code"]

        # Get materials for this SFT step
        cursor.execute("""
            SELECT
                m.id AS material_id,
                m.base_spec,
                m.variant,
                m.description AS material_description,
                m.notes AS material_notes
            FROM sft_material_links sml
            JOIN materials m ON sml.material_id = m.id
            WHERE sml.sft_id = (SELECT id FROM sft_steps WHERE sft_code = ?)
        """, (sft_code,))
        material_rows = cursor.fetchall()

        materials = []
        for mat_row in material_rows:
            material_id = mat_row["material_id"]

            # Get chemicals for this material
            cursor.execute("""
                SELECT
                    c.name,
                    c.cas,
                    c.hazard_flags,
                    c.default_hazard_level,
                    mc.pct_wt_low,
                    mc.pct_wt_high,
                    mc.notes AS composition_notes
                FROM material_chemicals mc
                JOIN chemicals c ON mc.chemical_id = c.id
                WHERE mc.material_id = ?
                ORDER BY c.default_hazard_level DESC, c.name ASC
            """, (material_id,))
            chemical_rows = cursor.fetchall()

            chemicals = []
            for chem_row in chemical_rows:
                # Parse hazard_flags JSON
                hazard_flags = None
                if chem_row["hazard_flags"]:
                    try:
                        hazard_flags = json.loads(chem_row["hazard_flags"])
                    except json.JSONDecodeError:
                        hazard_flags = {"error": "Invalid JSON", "raw": chem_row["hazard_flags"]}

                chemicals.append({
                    "name": chem_row["name"],
                    "cas": chem_row["cas"],
                    "pct_wt_low": chem_row["pct_wt_low"],
                    "pct_wt_high": chem_row["pct_wt_high"],
                    "hazard_flags": hazard_flags,
                    "default_hazard_level": chem_row["default_hazard_level"],
                    "composition_notes": chem_row["composition_notes"]
                })

            materials.append({
                "base_spec": mat_row["base_spec"],
                "variant": mat_row["variant"],
                "description": mat_row["material_description"],
                "notes": mat_row["material_notes"],
                "chemicals": chemicals
            })

        steps.append({
            "sft_code": sft_row["sft_code"],
            "step_order": sft_row["step_order"],
            "parent_group": sft_row["parent_group"],
            "description": sft_row["description"],
            "associated_specs": sft_row["associated_specs"],
            "source_doc": sft_row["source_doc"],
            "last_review": sft_row["last_review"],
            "notes": sft_row["notes"],
            "materials": materials
        })

    # Get provenance data (CSV SHAs and load timestamps)
    cursor.execute("""
        SELECT source_name, sha256, loaded_at
        FROM metadata_versions
        ORDER BY loaded_at DESC
    """)
    metadata_rows = cursor.fetchall()

    csv_shas = {}
    most_recent_load = None
    for meta_row in metadata_rows:
        csv_shas[meta_row["source_name"]] = meta_row["sha256"]
        if most_recent_load is None or meta_row["loaded_at"] > most_recent_load:
            most_recent_load = meta_row["loaded_at"]

    provenance = {
        "csv_shas": csv_shas,
        "loaded_at": most_recent_load or datetime.now().isoformat()
    }

    conn.close()

    # Build direct specifications if present (bypasses SFT steps)
    direct_specs = []
    if parsed["associated_specs"] and parsed["associated_specs"].strip():
        direct_specs = [s.strip() for s in parsed["associated_specs"].split(',') if s.strip()]

    # Also check finish_applied specs
    finish_applied_specs = []
    if parsed_row["finish_applied_specs"] and parsed_row["finish_applied_specs"].strip():
        finish_applied_specs = [s.strip() for s in parsed_row["finish_applied_specs"].split(',') if s.strip()]

    return {
        "finish_code": finish_code,
        "parsed": parsed,
        "direct_specs": direct_specs,  # Specifications directly linked to finish code (bypasses SFT)
        "finish_applied_specs": finish_applied_specs,  # Specifications from finish_applied
        "steps": steps,  # SFT steps (may be empty for some programs)
        "provenance": provenance
    }


def get_all_finish_codes(db_path: str = "data/hazardous_finishes.sqlite") -> list[dict[str, Any]]:
    """
    Retrieve list of all finish codes with descriptions.

    Args:
        db_path: Path to SQLite database

    Returns:
        List of dictionaries:
        [
            {
                "code": str,
                "description": str,
                "substrate": str,
                "finish_applied": str,
                "seq_id": int
            }
        ]

    Raises:
        FileNotFoundError: If database not found
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            fc.code,
            fc.description,
            s.description AS substrate,
            fa.description AS finish_applied,
            fc.seq_id,
            fc.source_doc,
            fc.program
        FROM finish_codes fc
        JOIN substrates s ON fc.substrate_id = s.id
        JOIN finish_applied fa ON fc.finish_applied_id = fa.id
        ORDER BY fc.code
    """)

    codes = []
    for row in cursor.fetchall():
        codes.append({
            "code": row["code"],
            "description": row["description"],
            "substrate": row["substrate"],
            "finish_applied": row["finish_applied"],
            "seq_id": row["seq_id"],
            "source_doc": row["source_doc"],
            "program": row["program"]
        })

    conn.close()
    return codes


def get_chemicals_by_hazard_level(
    db_path: str = "data/hazardous_finishes.sqlite",
    min_level: int = 1
) -> list[dict[str, Any]]:
    """
    Retrieve chemicals filtered by hazard level.

    Args:
        db_path: Path to SQLite database
        min_level: Minimum hazard level (1-5)

    Returns:
        List of chemical dictionaries sorted by hazard level descending

    Raises:
        FileNotFoundError: If database not found
        ValueError: If min_level out of range
    """
    if not 1 <= min_level <= 5:
        raise ValueError(f"min_level must be 1-5, got: {min_level}")

    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, cas, hazard_flags, default_hazard_level
        FROM chemicals
        WHERE default_hazard_level >= ?
        ORDER BY default_hazard_level DESC, name ASC
    """, (min_level,))

    chemicals = []
    for row in cursor.fetchall():
        hazard_flags = None
        if row["hazard_flags"]:
            try:
                hazard_flags = json.loads(row["hazard_flags"])
            except json.JSONDecodeError:
                hazard_flags = {"error": "Invalid JSON"}

        chemicals.append({
            "name": row["name"],
            "cas": row["cas"],
            "hazard_flags": hazard_flags,
            "default_hazard_level": row["default_hazard_level"]
        })

    conn.close()
    return chemicals


def get_all_specifications(db_path: str = "data/hazardous_finishes.sqlite") -> dict[str, Any]:
    """
    Extract all unique specifications from all SFT steps in the database.

    Args:
        db_path: Path to SQLite database

    Returns:
        Dictionary with structure:
        {
            "total_specs": int,
            "specifications": [
                {
                    "spec": str,
                    "sft_codes": [str, ...],  # Which SFT steps use this spec
                    "finish_codes": [str, ...],  # Which finish codes use this spec
                    "usage_count": int
                }
            ]
        }

    Raises:
        FileNotFoundError: If database file not found
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all SFT steps with their specifications
    cursor.execute("""
        SELECT DISTINCT
            sft.sft_code,
            sft.associated_specs
        FROM sft_steps sft
        WHERE sft.associated_specs IS NOT NULL
        AND sft.associated_specs != ''
        ORDER BY sft.sft_code
    """)

    sft_rows = cursor.fetchall()

    # Build specification map
    spec_map = {}  # spec -> {sft_codes: set, finish_codes: set}

    for row in sft_rows:
        sft_code = row["sft_code"]
        specs_raw = row["associated_specs"]

        # Split comma-separated specs
        individual_specs = [s.strip() for s in specs_raw.split(',') if s.strip()]

        for spec in individual_specs:
            if spec not in spec_map:
                spec_map[spec] = {
                    "sft_codes": set(),
                    "finish_codes": set()
                }
            spec_map[spec]["sft_codes"].add(sft_code)

    # Now find which finish codes use each spec (via SFT steps)
    for spec in spec_map.keys():
        # Get all finish codes that use any of the SFT steps containing this spec
        sft_codes_for_spec = list(spec_map[spec]["sft_codes"])
        if sft_codes_for_spec:
            placeholders = ','.join('?' * len(sft_codes_for_spec))
            query = f"""
                SELECT DISTINCT fc.code
                FROM finish_codes fc
                JOIN finish_code_steps fcs ON fc.id = fcs.finish_code_id
                JOIN sft_steps sft ON fcs.sft_id = sft.id
                WHERE sft.sft_code IN ({placeholders})
                ORDER BY fc.code
            """
            cursor.execute(query, sft_codes_for_spec)
            for fc_row in cursor.fetchall():
                spec_map[spec]["finish_codes"].add(fc_row["code"])

    conn.close()

    # Convert to output format
    specifications = []
    for spec, data in sorted(spec_map.items()):
        specifications.append({
            "spec": spec,
            "sft_codes": sorted(list(data["sft_codes"])),
            "finish_codes": sorted(list(data["finish_codes"])),
            "usage_count": len(data["finish_codes"])
        })

    # Sort by usage count descending
    specifications.sort(key=lambda x: (-x["usage_count"], x["spec"]))

    return {
        "total_specs": len(specifications),
        "specifications": specifications
    }


def get_finish_code_specs(finish_code: str, db_path: str = "data/hazardous_finishes.sqlite") -> dict[str, Any]:
    """
    Extract all unique specifications referenced in a finish code's SFT steps.

    Args:
        finish_code: Finish code to query (e.g., "BP27")
        db_path: Path to SQLite database

    Returns:
        Dictionary with structure:
        {
            "finish_code": str,
            "specifications": [str, ...],  # Unique specs, sorted
            "spec_count": int,
            "steps_with_specs": [
                {
                    "sft_code": str,
                    "step_order": int,
                    "associated_specs": str,
                    "description": str (truncated to 80 chars)
                }
            ]
        }

        If finish_code not found, returns error structure like get_finish_code_tree()

    Raises:
        FileNotFoundError: If database file not found
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if finish code exists
    cursor.execute("SELECT id FROM finish_codes WHERE code = ?", (finish_code,))
    fc_row = cursor.fetchone()

    if not fc_row:
        # Return error with available codes
        cursor.execute("SELECT code FROM finish_codes ORDER BY code LIMIT 10")
        available = [row[0] for row in cursor.fetchall()]
        conn.close()
        return {
            "error": "Finish code not found",
            "finish_code": finish_code,
            "available_codes": available
        }

    # Get all SFT steps with specifications
    cursor.execute("""
        SELECT
            sft.sft_code,
            sft.associated_specs,
            sft.description,
            fcs.step_order
        FROM finish_code_steps fcs
        JOIN sft_steps sft ON fcs.sft_id = sft.id
        WHERE fcs.finish_code_id = ?
        ORDER BY fcs.step_order
    """, (fc_row["id"],))

    sft_rows = cursor.fetchall()
    conn.close()

    # Collect unique specifications
    # Split comma-separated specs since they represent alternatives (OR relationship)
    specs_set = set()
    steps_with_specs = []

    for row in sft_rows:
        specs_raw = row["associated_specs"]
        if specs_raw and specs_raw.strip():
            # Split by comma to get individual specs
            individual_specs = [s.strip() for s in specs_raw.split(',') if s.strip()]

            # Add each individual spec to the set
            for spec in individual_specs:
                specs_set.add(spec)

            # Truncate description for display
            desc = row["description"]
            if len(desc) > 80:
                desc = desc[:77] + "..."

            steps_with_specs.append({
                "sft_code": row["sft_code"],
                "step_order": row["step_order"],
                "associated_specs": specs_raw.strip(),  # Keep original grouped format
                "associated_specs_list": individual_specs,  # Also provide as list
                "description": desc
            })

    # Sort specifications
    specs_list = sorted(specs_set)

    return {
        "finish_code": finish_code,
        "specifications": specs_list,
        "spec_count": len(specs_list),
        "steps_with_specs": steps_with_specs
    }
