# Hazardous Finishes - Implementation Checklist

**Owner**: Internal Team
**Created**: 2025-11-03
**Last Updated**: 2025-11-03

---

## Phase 0 - Init and Scaffolding

### Environment Setup
- [x] Create `.gitignore` for Python, SQLite, venv, Streamlit
- [x] Create `pyproject.toml` with pinned dependencies
- [ ] Test installation: `python -m venv .venv && source .venv/bin/activate && pip install -e .`
- [ ] Verify all imports work: `python -c "import pandas, sqlite_utils, sqlalchemy, typer, streamlit, regex"`

### Documentation
- [x] Create `docs/README_architecture.md` (architecture overview)
- [x] Create `docs/schema_overview.md` (ERD + CSV contracts)
- [x] Verify `docs/process_flow.md` exists (already present)
- [x] Create `init/SCOPE.md` (MVP scope, deferrals, decisions)
- [x] Create `init/TODO.md` (this file)
- [ ] Create `README.md` (quickstart + commands)

### Status
Phase 0: **IN PROGRESS** (75% complete - pending README.md and environment test)

---

## Phase 1 - Database Schema + ETL Ingestion

### Database Schema
- [ ] Create `db/schema.sql` with tables:
  - [ ] `substrates` (id, code UNIQUE, description)
  - [ ] `finish_applied` (id, code UNIQUE, description)
  - [ ] `finish_codes` (id, code UNIQUE, substrate_id FK, finish_applied_id FK, seq_id, description, notes)
  - [ ] `sft_steps` (id, sft_code UNIQUE, title, description, revision, source_doc, last_review)
  - [ ] `finish_code_steps` (id, finish_code_id FK, sft_id FK, step_order)
  - [ ] `materials` (id, base_spec, variant, description, notes)
  - [ ] `sft_material_links` (id, sft_id FK, material_id FK, note)
  - [ ] `chemicals` (id, name, cas UNIQUE, hazard_flags, default_hazard_level)
  - [ ] `material_chemicals` (id, material_id FK, chemical_id FK, pct_wt_low, pct_wt_high, notes)
  - [ ] `spec_dependencies` (id, spec_material_id FK, ref_spec_material_id FK, relation) [OPTIONAL]
  - [ ] `metadata_versions` (id, source_name UNIQUE, sha256, rows_loaded, loaded_at)
- [ ] Add indexes:
  - [ ] `idx_finish_codes_substrate`
  - [ ] `idx_finish_codes_finish_applied`
  - [ ] `idx_finish_code_steps_finish`
  - [ ] `idx_finish_code_steps_sft`
  - [ ] `idx_sft_material_links_sft`
  - [ ] `idx_material_chemicals_material`
- [ ] Enable foreign key constraints: `PRAGMA foreign_keys = ON;`

### ETL Implementation
- [ ] Create `etl/__init__.py`
- [ ] Create `etl/hashing.py`:
  - [ ] Function: `compute_sha256(file_path: str) -> str`
  - [ ] Unit test with known hash
- [ ] Create `etl/validators.py`:
  - [ ] Function: `validate_referential_integrity(conn) -> list[dict]`
  - [ ] Function: `validate_completeness(conn) -> list[dict]`
  - [ ] Function: `validate_formats(conn) -> list[dict]` (CAS, JSON, ranges)
  - [ ] Function: `generate_validation_report(errors, warnings) -> dict`
  - [ ] Unit tests for each validator
- [ ] Create `etl/load_csvs.py`:
  - [ ] Function: `load_substrates(csv_path, conn)`
  - [ ] Function: `load_finish_applied(csv_path, conn)`
  - [ ] Function: `load_finish_codes(csv_path, conn)`
  - [ ] Function: `load_sft_steps(csv_path, conn)`
  - [ ] Function: `load_finish_code_steps(csv_path, conn)`
  - [ ] Function: `load_materials(csv_path, conn)`
  - [ ] Function: `load_sft_material_links(csv_path, conn)`
  - [ ] Function: `load_chemicals(csv_path, conn)`
  - [ ] Function: `load_material_chemicals(csv_path, conn)`
  - [ ] Function: `record_metadata(source_name, sha256, rows, conn)`
  - [ ] Main orchestrator: `ingest_all(input_dir, db_path) -> dict`
  - [ ] Generate `data/outputs/ingest_report.json`

### Test Fixtures
- [ ] Create `tests/fixtures/substrates.csv` (3 rows)
- [ ] Create `tests/fixtures/finish_applied.csv` (3 rows)
- [ ] Create `tests/fixtures/finish_codes.csv` (2 rows)
- [ ] Create `tests/fixtures/sft_steps.csv` (3 rows)
- [ ] Create `tests/fixtures/finish_code_steps.csv` (4 rows)
- [ ] Create `tests/fixtures/materials_map.csv` (2 rows)
- [ ] Create `tests/fixtures/sft_material_links.csv` (2 rows)
- [ ] Create `tests/fixtures/chemicals.csv` (3 rows with fake hazard data)
- [ ] Create `tests/fixtures/material_chemicals.csv` (4 rows with fake %wt)
- [ ] Document fixture scenario in `tests/fixtures/README.md`

### Testing
- [ ] Create `tests/__init__.py`
- [ ] Create `tests/test_etl.py`:
  - [ ] Test: `test_load_all_fixtures_success()`
  - [ ] Test: `test_referential_integrity_orphan_detection()`
  - [ ] Test: `test_validation_report_generation()`
  - [ ] Test: `test_duplicate_code_handling()`
- [ ] All tests pass: `pytest tests/test_etl.py -v`

### Integration
- [ ] Successfully ingest fixtures: `hazard-cli ingest --input tests/fixtures`
- [ ] Verify `db/engine.sqlite` created and populated
- [ ] Verify `data/outputs/ingest_report.json` generated with counts and SHAs
- [ ] Run validators: `hazard-cli validate` (no errors on fixtures)

### Status
Phase 1: **NOT STARTED**

---

## Phase 2 - Query Engine + CLI

### Query Engine
- [ ] Create `app/__init__.py`
- [ ] Create `app/services/__init__.py`
- [ ] Create `app/services/query.py`:
  - [ ] Function: `get_finish_code_tree(finish_code: str, db_path: str) -> dict`
    - [ ] Return structure:
      ```
      {
        "finish_code": str,
        "parsed": {
          "substrate": {"code": str, "description": str},
          "finish_applied": {"code": str, "description": str},
          "seq_id": int,
          "finish_description": str
        },
        "steps": [
          {
            "sft_code": str,
            "step_order": int,
            "title": str,
            "description": str,
            "materials": [
              {
                "base_spec": str,
                "variant": str | null,
                "description": str,
                "chemicals": [
                  {
                    "name": str,
                    "cas": str,
                    "pct_wt_low": float,
                    "pct_wt_high": float,
                    "hazard_flags": dict,
                    "default_hazard_level": int
                  }
                ]
              }
            ]
          }
        ],
        "provenance": {
          "csv_shas": {"substrates.csv": str, ...},
          "loaded_at": str (ISO datetime)
        }
      }
      ```
  - [ ] Handle missing finish code gracefully (return error dict)
  - [ ] Unit tests with fixture database

### CLI Implementation
- [ ] Create `app/cli.py`:
  - [ ] Command: `ingest --input DIR --db PATH` (calls ETL)
  - [ ] Command: `validate --db PATH` (runs validators, prints report)
  - [ ] Command: `show FINISH_CODE --db PATH` (prints JSON tree)
  - [ ] Global option: `--db PATH` (default: `db/engine.sqlite`)
  - [ ] Setup Typer app with help text
  - [ ] Entry point in `pyproject.toml`: `hazard-cli = "app.cli:app"`
- [ ] Test all CLI commands manually:
  - [ ] `hazard-cli --help`
  - [ ] `hazard-cli ingest --input tests/fixtures`
  - [ ] `hazard-cli validate`
  - [ ] `hazard-cli show BP27` (use fixture code)

### Documentation Updates
- [ ] Update `README.md` with:
  - [ ] Installation instructions
  - [ ] Quickstart example (ingest + show)
  - [ ] CLI command reference
  - [ ] Example JSON output
  - [ ] Troubleshooting section

### Testing
- [ ] Create `tests/test_query.py`:
  - [ ] Test: `test_get_finish_code_tree_success()`
  - [ ] Test: `test_get_finish_code_tree_missing_code()`
  - [ ] Test: `test_provenance_includes_shas()`
  - [ ] Test: `test_chemicals_sorted_by_hazard_level()`
- [ ] All tests pass: `pytest tests/ -v`

### Integration
- [ ] End-to-end test: ingest fixtures ’ query via CLI ’ verify JSON structure
- [ ] Validate JSON schema matches spec
- [ ] Test with missing/incomplete data (ensure graceful errors)

### Status
Phase 2: **NOT STARTED**

---

## Phase 3 - Proposal Tool (Regex-Based Material Extraction)

### Implementation
- [ ] Create `app/services/propose_materials.py`:
  - [ ] Regex patterns for spec extraction:
    - [ ] `\b(?:MIL|AMS|ASTM|LMA|P[JG]?\d{2,}|MR\d{3,}|P\d{5})[-A-Z0-9 /,()]*\b`
  - [ ] Regex patterns for variant extraction:
    - [ ] `(TYPE\s*[IVX0-9]+|CLASS\s*\d+[A-Z]?|UNSEALED|SEALED|BLACK|GRAY|WHITE)`
  - [ ] Function: `extract_specs_from_description(description: str) -> list[dict]`
  - [ ] Function: `propose_materials_for_all_sfts(db_path: str) -> pd.DataFrame`
  - [ ] Output columns: `sft_code, candidate_text, base_spec_guess, variant_guess, context, confidence, notes`
  - [ ] Confidence scoring (1-5 based on pattern match strength)
  - [ ] Write to `data/outputs/materials_map_proposed.csv`
- [ ] Add CLI command: `propose-sft-materials --db PATH --output PATH`
- [ ] Document workflow in `docs/process_flow.md`

### Testing
- [ ] Create `tests/test_propose.py`:
  - [ ] Test: `test_extract_mil_spec()`
  - [ ] Test: `test_extract_variant()`
  - [ ] Test: `test_confidence_scoring()`
  - [ ] Test: `test_no_false_positives_on_plain_text()`
- [ ] Manual review of proposals on fixtures

### Status
Phase 3: **DEFERRED** (not required for MVP)

---

## Phase 4 - Streamlit GUI

### Implementation
- [ ] Create `app/streamlit_app.py`:
  - [ ] Page title: "Hazardous Finishes Lookup"
  - [ ] Text input: `finish_code`
  - [ ] Button: "Lookup"
  - [ ] On click:
    - [ ] Call `get_finish_code_tree()`
    - [ ] Display error if code not found
  - [ ] Display sections:
    - [ ] **Parsed Code**: substrate, finish applied, seq_id with descriptions
    - [ ] **SFT Steps**: Accordion/expander per step
      - [ ] Show step title, description
      - [ ] Table of materials per step (base_spec, variant)
      - [ ] Table of chemicals per material (name, CAS, %wt, hazard flags)
  - [ ] **Traceability Footer**:
    - [ ] CSV SHAs (collapsible)
    - [ ] Load timestamp
  - [ ] **Future Placeholders** (disabled):
    - [ ] Surface area input (m²)
    - [ ] Coating density input (g/m²)
    - [ ] Note: "Mass calculation coming in Phase 5"
- [ ] Use `st.cache_data` for database connection
- [ ] Add error handling for database connection failures

### Testing
- [ ] Manual test: `streamlit run app/streamlit_app.py`
- [ ] Test with fixture finish code
- [ ] Test with invalid finish code (verify error message)
- [ ] Test responsiveness (expand/collapse accordions)

### Documentation
- [ ] Add Streamlit usage to `README.md`:
  - [ ] Launch command
  - [ ] Expected behavior
  - [ ] Screenshots (optional)

### Status
Phase 4: **NOT STARTED**

---

## Phase 5+ - Deferred Features

### Part Number Integration (Phase 5)
- [ ] Add `parts` table to schema
- [ ] Extend ETL for `parts.csv`
- [ ] Batch export: part numbers ’ chemical rollup
- [ ] Mass calculation: surface area × coating density × %wt

### REST API (Phase 6)
- [ ] FastAPI implementation
- [ ] Endpoints: `/finish/{code}`, `/health`
- [ ] OpenAPI docs
- [ ] Optional: authentication

### Drift Control (Phase 7)
- [ ] CSV SHA comparison tool
- [ ] Diff report generation
- [ ] GitHub Actions workflow for nightly validation
- [ ] Notification system (email/Slack)

### Status
Phases 5-7: **DEFERRED** (post-MVP)

---

## Cross-Cutting Tasks

### Code Quality
- [ ] Add type hints to all functions
- [ ] Format code: `black .`
- [ ] Lint code: `ruff check .`
- [ ] Docstrings for all public functions (Google style)
- [ ] No `# type: ignore` comments without justification

### Testing
- [ ] Test coverage e80%: `pytest --cov=app --cov=etl tests/`
- [ ] All tests pass in CI (future)
- [ ] No skipped tests without JIRA ticket reference

### Documentation
- [ ] All commands documented in `README.md`
- [ ] CSV contracts documented in `docs/schema_overview.md`
- [ ] Architecture decisions documented in ADR format (future)
- [ ] CHANGELOG.md for version tracking (future)

### Security
- [ ] Audit `.gitignore` to ensure no proprietary data committed
- [ ] Review test fixtures for proprietary data leaks
- [ ] SQL injection prevention (use parameterized queries only)
- [ ] No hardcoded credentials in code

---

## Blockers & Risks

| ID | Blocker | Impact | Owner | Status |
|----|---------|--------|-------|--------|
| B1 | Missing production CSV samples | High | Domain experts | Open |
| B2 | Unclear hazard flag schema | Medium | Safety team | Resolved (use GHS codes) |
| B3 | Proprietary data in test fixtures | Critical | Dev team | Mitigated (fake data only) |

---

## Definition of Done (Per Phase)

- [ ] All phase tasks checked off
- [ ] All tests passing (`pytest`)
- [ ] Code formatted (`black .`)
- [ ] Code linted (`ruff check .`)
- [ ] Documentation updated (`README.md`, `docs/`)
- [ ] `init/TODO.md` updated with status
- [ ] `init/SCOPE.md` updated with deliverables
- [ ] Git commit with clear message
- [ ] Peer review (if applicable)

---

## Next Actions

**Immediate**:
1. Complete Phase 0: Create `README.md` and test environment setup
2. Begin Phase 1: Create `db/schema.sql`

**This Week**:
- Complete Phase 1 (schema + ETL)
- Begin Phase 2 (query engine)

**This Sprint**:
- Complete Phase 2 (CLI)
- Begin Phase 4 (Streamlit GUI)

---

**Last Updated**: 2025-11-03
**Current Phase**: Phase 0 (75% complete)
**Next Milestone**: Phase 1 schema creation
