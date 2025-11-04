# Hazardous Finishes - Architecture Overview

## Purpose
A deterministic data engine that maps **Finish Codes → SFT Steps → Materials → Chemicals** with hazard flagging. Built for traceability, compliance, and safety analysis of surface finishing processes.

## Core Principles

### 1. Deterministic Only
- **NO AI** in core ingestion or query flows
- All mappings are human-curated via CSV inputs
- Regex-based proposal tools may suggest links but require manual approval
- Fail-fast validation on referential integrity errors

### 2. CSV-Driven Data Pipeline
- All source data ingested from versioned CSV files in `data/inputs/`
- SHA256 hashing tracks data lineage and drift
- Human-readable validation reports flag issues before commit
- Proprietary chemical compositions remain internal (not in git)

### 3. SQLite as Single Source of Truth
- Normalized relational schema in `db/engine.sqlite`
- Foreign key constraints enforced
- Simple, portable, version-controllable (schema only)

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA INPUTS (CSVs)                      │
│  substrates.csv, finish_applied.csv, finish_codes.csv,     │
│  sft_steps.csv, materials_map.csv, chemicals.csv, etc.     │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │   ETL Layer (etl/)  │
        │  - load_csvs.py     │
        │  - validators.py    │
        │  - hashing.py       │
        └──────────┬──────────┘
                   │
                   ▼
         ┌──────────────────┐
         │  SQLite Database │
         │  db/engine.sqlite│
         └────────┬─────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│ Query Engine │    │ Proposal Tool│
│ (services/)  │    │ (services/)  │
└──────┬───────┘    └──────┬───────┘
       │                   │
   ┌───┴────┐         ┌────┴────┐
   ▼        ▼         ▼         ▼
┌─────┐  ┌──────┐  ┌────────────┐
│ CLI │  │  GUI │  │ CSV Export │
│     │  │(Streamlit) │ (proposed) │
└─────┘  └──────┘  └────────────┘
```

## Component Breakdown

### ETL Layer (`etl/`)
- **load_csvs.py**: Orchestrates CSV ingestion, upserts data, records SHA256 hashes
- **validators.py**: Referential integrity checks, completeness checks, orphan detection
- **hashing.py**: File fingerprinting for drift detection

### Database Layer (`db/`)
- **schema.sql**: DDL for all tables (substrates, finish_codes, sft_steps, materials, chemicals, etc.)
- **engine.sqlite**: Runtime database (not committed to git)

### Application Layer (`app/`)
- **services/query.py**: Core query engine - `get_finish_code_tree(code)` returns hierarchical JSON
- **services/propose_materials.py**: Regex-based spec/material extraction from SFT descriptions
- **cli.py**: Typer-based CLI for ingest, validate, show, propose commands
- **streamlit_app.py**: MVP GUI for single finish code lookup with traceability

### Data Flow

1. **Ingestion**: User places CSVs in `data/inputs/` → runs `hazard-cli ingest`
2. **Validation**: ETL validates references, writes `data/outputs/ingest_report.json`
3. **Query**: User queries via CLI (`hazard-cli show BP27`) or GUI
4. **Traceability**: Every response includes CSV SHA256s and load timestamps

## Data Hierarchy

```
Finish Code (e.g., BP27)
  ├─ Parsed Components
  │   ├─ Substrate (B = "BRASS")
  │   ├─ Finish Applied (P = "PASSIVATE")
  │   └─ Sequence ID (27)
  └─ SFT Steps (ordered)
      ├─ Step 1: SFT-BRASS-DEGREASE
      │   └─ Materials
      │       └─ MIL-PRF-8625 TYPE III
      │           └─ Chemicals
      │               ├─ Chromic Acid (CAS 7738-94-5) - CARCINOGEN
      │               └─ Sulfuric Acid (CAS 7664-93-9) - CORROSIVE
      └─ Step 2: SFT-PASSIVATE-SEAL
          └─ ...
```

## Key Design Decisions

### Why SQLite?
- Zero infrastructure overhead
- ACID compliance with FK constraints
- Portable single-file database
- Schema versioning via DDL in git

### Why CSV Input?
- Human-editable in Excel/Sheets for non-technical stakeholders
- Version-controllable diffs (schema/code only; data SHAs tracked separately)
- Simple audit trail via file hashes

### Why No AI in MVP?
- Guarantees reproducibility and explainability
- Avoids hallucination risk in safety-critical domain
- Regex proposal tool provides deterministic suggestions with human approval

## Security & Proprietary Data

- **Chemical compositions** (pct_wt ranges) are proprietary and must not be committed to git
- Use `.gitignore` to exclude `data/inputs/*.csv` and `db/*.sqlite`
- Test fixtures use fake/non-proprietary data only
- Validation reports may be committed but should not leak chemical weights

## Roadmap Phases

- **Phase 0**: Scaffolding, docs, dependencies ✅
- **Phase 1**: Database schema + ETL ingestion
- **Phase 2**: Query engine + CLI
- **Phase 3**: Proposal tool (regex-based)
- **Phase 4**: Streamlit GUI
- **Phase 5**: Part number integration (deferred)
- **Phase 6**: REST API (deferred)
- **Phase 7**: Drift control automation (deferred)

## Technology Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| Database | SQLite 3 |
| ORM/Query | SQLAlchemy, sqlite-utils |
| CLI | Typer |
| GUI | Streamlit |
| Data Processing | Pandas |
| Hashing | hashlib (SHA256) |
| Validation | Custom validators with regex |
| Testing | pytest |

## API Contracts (Future)

### CLI Commands
```bash
hazard-cli ingest              # Load CSVs into SQLite
hazard-cli validate            # Run integrity checks
hazard-cli show BP27           # Display finish code tree
hazard-cli propose-sft-materials  # Generate material suggestions
```

### Query Response Schema
See `services/query.py` for full JSON structure.

## Extension Points

- **Custom validators**: Add new checks in `etl/validators.py`
- **New CSV sources**: Extend `etl/load_csvs.py` with new table loaders
- **Export formats**: Add PDF/Excel exporters in `app/services/export.py`
- **Batch processing**: Extend query engine for multiple finish codes

## Testing Strategy

- Unit tests for ETL validators with fixture CSVs
- Integration tests for full ingest → query flow
- No mocked databases - use real SQLite in-memory for speed
- Fixtures in `tests/fixtures/` use non-proprietary fake data

## Performance Considerations

- Current scope: <10,000 finish codes, <1,000 SFT steps
- Indexes on `code` columns for fast lookups
- Denormalization deferred until performance issues arise
- Streamlit caching for repeated queries

## Compliance & Audit Trail

- Every ingest records: source file, SHA256, row count, timestamp
- Validation reports provide human-readable error logs
- Future: diff reports for CSV changes between versions
