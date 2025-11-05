-- Hazardous Finishes Database Schema
-- SQLite 3 DDL
-- Version: 1.0.0
-- Last Updated: 2025-11-03

-- Enable foreign key constraints (must be set per connection)
PRAGMA foreign_keys = ON;

-- =============================================================================
-- CORE TABLES: Finish Code Components
-- =============================================================================

-- Substrate types (base materials receiving finishes)
CREATE TABLE IF NOT EXISTS substrates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Finish types applied to substrates
CREATE TABLE IF NOT EXISTS finish_applied (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Composite finish codes (substrate + finish + sequence)
CREATE TABLE IF NOT EXISTS finish_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    substrate_id INTEGER NOT NULL,
    finish_applied_id INTEGER NOT NULL,
    seq_id INTEGER NOT NULL,
    description TEXT,
    notes TEXT,
    source_doc TEXT,
    program TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (substrate_id) REFERENCES substrates(id) ON DELETE RESTRICT,
    FOREIGN KEY (finish_applied_id) REFERENCES finish_applied(id) ON DELETE RESTRICT
);

-- =============================================================================
-- SFT (Standard Finish Templates) TABLES
-- =============================================================================

-- Reusable process steps
CREATE TABLE IF NOT EXISTS sft_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sft_code TEXT NOT NULL UNIQUE,
    parent_group TEXT,
    description TEXT NOT NULL,
    associated_specs TEXT,
    source_doc TEXT,
    last_review TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Junction table: finish codes → ordered SFT steps
CREATE TABLE IF NOT EXISTS finish_code_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finish_code_id INTEGER NOT NULL,
    sft_id INTEGER NOT NULL,
    step_order INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (finish_code_id) REFERENCES finish_codes(id) ON DELETE RESTRICT,
    FOREIGN KEY (sft_id) REFERENCES sft_steps(id) ON DELETE RESTRICT,
    UNIQUE (finish_code_id, sft_id),
    UNIQUE (finish_code_id, step_order)
);

-- =============================================================================
-- MATERIALS AND SPECIFICATIONS
-- =============================================================================

-- Material specifications (base spec + optional variant)
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base_spec TEXT NOT NULL,
    variant TEXT,
    description TEXT,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (base_spec, variant)
);

-- Junction table: SFT steps → materials
CREATE TABLE IF NOT EXISTS sft_material_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sft_id INTEGER NOT NULL,
    material_id INTEGER NOT NULL,
    note TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sft_id) REFERENCES sft_steps(id) ON DELETE RESTRICT,
    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE RESTRICT
);

-- Optional: spec-to-spec dependencies (e.g., "MIL-PRF-8625 calls out ASTM B633")
CREATE TABLE IF NOT EXISTS spec_dependencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_material_id INTEGER NOT NULL,
    ref_spec_material_id INTEGER NOT NULL,
    relation TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (spec_material_id) REFERENCES materials(id) ON DELETE RESTRICT,
    FOREIGN KEY (ref_spec_material_id) REFERENCES materials(id) ON DELETE RESTRICT
);

-- =============================================================================
-- CHEMICALS AND HAZARDS
-- =============================================================================

-- Chemical inventory with hazard classifications
CREATE TABLE IF NOT EXISTS chemicals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cas TEXT UNIQUE,
    hazard_flags TEXT,
    default_hazard_level INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CHECK (default_hazard_level IS NULL OR (default_hazard_level >= 1 AND default_hazard_level <= 5))
);

-- Chemical composition of materials (weight percentage ranges)
CREATE TABLE IF NOT EXISTS material_chemicals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_id INTEGER NOT NULL,
    chemical_id INTEGER NOT NULL,
    pct_wt_low REAL,
    pct_wt_high REAL,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE RESTRICT,
    FOREIGN KEY (chemical_id) REFERENCES chemicals(id) ON DELETE RESTRICT,
    CHECK (pct_wt_low IS NULL OR pct_wt_low >= 0),
    CHECK (pct_wt_high IS NULL OR pct_wt_high <= 100),
    CHECK (pct_wt_low IS NULL OR pct_wt_high IS NULL OR pct_wt_low <= pct_wt_high)
);

-- =============================================================================
-- METADATA AND VERSIONING
-- =============================================================================

-- Tracks CSV ingestion history for lineage and drift detection
CREATE TABLE IF NOT EXISTS metadata_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    rows_loaded INTEGER NOT NULL,
    loaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- INDEXES FOR QUERY PERFORMANCE
-- =============================================================================

-- Finish codes lookup
CREATE INDEX IF NOT EXISTS idx_finish_codes_substrate
    ON finish_codes(substrate_id);
CREATE INDEX IF NOT EXISTS idx_finish_codes_finish_applied
    ON finish_codes(finish_applied_id);
CREATE INDEX IF NOT EXISTS idx_finish_codes_code
    ON finish_codes(code);

-- Finish code steps traversal
CREATE INDEX IF NOT EXISTS idx_finish_code_steps_finish
    ON finish_code_steps(finish_code_id);
CREATE INDEX IF NOT EXISTS idx_finish_code_steps_sft
    ON finish_code_steps(sft_id);
CREATE INDEX IF NOT EXISTS idx_finish_code_steps_order
    ON finish_code_steps(finish_code_id, step_order);

-- SFT material links
CREATE INDEX IF NOT EXISTS idx_sft_material_links_sft
    ON sft_material_links(sft_id);
CREATE INDEX IF NOT EXISTS idx_sft_material_links_material
    ON sft_material_links(material_id);

-- Material chemicals lookup
CREATE INDEX IF NOT EXISTS idx_material_chemicals_material
    ON material_chemicals(material_id);
CREATE INDEX IF NOT EXISTS idx_material_chemicals_chemical
    ON material_chemicals(chemical_id);

-- Chemical lookups
CREATE INDEX IF NOT EXISTS idx_chemicals_cas
    ON chemicals(cas);
CREATE INDEX IF NOT EXISTS idx_chemicals_name
    ON chemicals(name);

-- =============================================================================
-- VIEWS FOR COMMON QUERIES (Optional, for convenience)
-- =============================================================================

-- View: All finish codes with parsed components
CREATE VIEW IF NOT EXISTS v_finish_codes_expanded AS
SELECT
    fc.id,
    fc.code,
    fc.seq_id,
    fc.description AS finish_description,
    fc.notes,
    fc.source_doc,
    fc.program,
    s.code AS substrate_code,
    s.description AS substrate_description,
    fa.code AS finish_applied_code,
    fa.description AS finish_applied_description
FROM finish_codes fc
JOIN substrates s ON fc.substrate_id = s.id
JOIN finish_applied fa ON fc.finish_applied_id = fa.id;

-- View: All chemicals with highest hazard first
CREATE VIEW IF NOT EXISTS v_chemicals_by_hazard AS
SELECT
    id,
    name,
    cas,
    hazard_flags,
    default_hazard_level
FROM chemicals
ORDER BY default_hazard_level DESC, name ASC;

-- =============================================================================
-- SCHEMA METADATA
-- =============================================================================

-- Track schema version for migrations
CREATE TABLE IF NOT EXISTS schema_version (
    version TEXT PRIMARY KEY,
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

-- Insert initial schema version
INSERT OR IGNORE INTO schema_version (version, description)
VALUES ('1.0.0', 'Initial schema with all core tables, indexes, and views');
