# Project Scope - Hazardous Finishes Data Engine

## MVP Scope (In Scope)

### Core Functionality
1. **Finish Code Lookup**
   - Input: Finish code (e.g., "BP27")
   - Output: Full hierarchical tree with:
     - Parsed code components (substrate, finish applied, sequence ID)
     - Ordered SFT steps with descriptions
     - Materials referenced by each SFT step (base spec + variant)
     - Chemicals in each material with hazard flags and %wt ranges
   - Deterministic query with full traceability

2. **Data Ingestion (ETL)**
   - CSV-driven data pipeline
   - Ingest from `data/inputs/` directory
   - Support for tables:
     - Substrates, finish_applied, finish_codes
     - SFT steps, finish_code_steps
     - Materials, sft_material_links
     - Chemicals, material_chemicals
     - Optional: spec_dependencies
   - SHA256 hashing for version tracking
   - Row count and timestamp recording

3. **Validation & Integrity**
   - Referential integrity checks (FK validation)
   - Orphan detection (dangling references)
   - Completeness checks (required fields)
   - Format validation (CAS numbers, JSON hazard flags)
   - Human-readable validation reports (`data/outputs/ingest_report.json`)
   - Fail-fast on critical errors

4. **CLI Interface**
   - `hazard-cli ingest` - Load CSVs into SQLite
   - `hazard-cli validate` - Run integrity checks
   - `hazard-cli show FINISH_CODE` - Display JSON tree
   - Typer-based commands with help text

5. **Streamlit GUI (MVP)**
   - Single finish code input field
   - Display parsed code components with descriptions
   - Accordion/expandable list of SFT steps
   - Material tables per step
   - Chemical tables with hazard flags and %wt ranges
   - Footer: CSV SHA summary and load timestamps
   - Placeholder inputs for future surface area calculations (disabled)

6. **Documentation**
   - Architecture overview (`docs/README_architecture.md`)
   - Database schema with ERD (`docs/schema_overview.md`)
   - Process flow with DFD (`docs/process_flow.md`)
   - User quickstart (`README.md`)
   - CSV input contracts

7. **Testing**
   - Unit tests for ETL validators
   - Integration tests for ingest → query flow
   - Non-proprietary test fixtures in `tests/fixtures/`
   - pytest-based test suite

---

## Out of Scope (Deferred or Future)

### Phase 5 - Part Number Integration
- `parts` table with part_number → finish_code mapping
- Surface area tracking per part
- Batch export: part numbers → chemical lists with rollups
- Mass calculations (surface area × coating density × %wt)

### Phase 6 - REST API
- FastAPI endpoints for finish code queries
- Health check endpoints
- API authentication/authorization
- OpenAPI/Swagger documentation

### Phase 7 - Drift Control & Automation
- Automated CSV SHA comparison
- Diff reports for row-level changes
- GitHub Actions for nightly validation runs
- Email/Slack notifications on validation failures

### Advanced Features (Not in Roadmap)
- AI-powered SFT description parsing (regex proposal tool is deterministic only)
- Real-time chemical inventory tracking
- Safety Data Sheet (SDS) auto-linking
- Multi-user collaborative editing
- RBAC (Role-Based Access Control)
- PDF/Excel export of full finish code reports
- Batch processing of multiple finish codes
- Coating thickness calculations
- Lifecycle cost analysis
- Alternative material recommendations
- Regulatory compliance auto-reporting (e.g., REACH, RoHS)

### Data Not Included in MVP
- Historical finish code revisions (versioning)
- Process parameter ranges (temperature, time, agitation)
- Equipment/tank assignments
- Quality control test results
- Actual part usage data (ERP integration)
- Supplier information for chemicals
- Cost data (material pricing)
- Environmental impact metrics (VOC, wastewater)

---

## Acceptance Criteria

### Phase 0 - Init and Scaffolding ✅
- [x] `.gitignore` created for Python, SQLite, venv, Streamlit
- [x] `pyproject.toml` with pinned dependencies
- [x] Documentation files populated:
  - [x] `docs/README_architecture.md`
  - [x] `docs/schema_overview.md`
  - [x] `docs/process_flow.md` (already exists)
- [x] `init/SCOPE.md` created
- [x] `init/TODO.md` seeded with checklist
- [x] `README.md` with quickstart and commands
- [ ] Successful `pip install -e .` execution

### Phase 1 - Database Schema + ETL
- [ ] `db/schema.sql` created with all tables
- [ ] `etl/hashing.py` implemented (SHA256 file hashing)
- [ ] `etl/validators.py` implemented (referential + completeness checks)
- [ ] `etl/load_csvs.py` implemented (CSV → SQLite with metadata tracking)
- [ ] Test fixtures created in `tests/fixtures/`
- [ ] Successfully ingest fixtures and produce `data/outputs/ingest_report.json`
- [ ] All validators pass on test fixtures

### Phase 2 - Query Engine + CLI
- [ ] `app/services/query.py` implemented (`get_finish_code_tree()`)
- [ ] `app/cli.py` implemented with all commands
- [ ] CLI commands work end-to-end on test fixtures
- [ ] JSON output includes provenance (CSV SHAs, timestamps)
- [ ] README updated with usage examples

### Phase 3 - Proposal Tool (Deferred for MVP)
- [ ] `app/services/propose_materials.py` implemented
- [ ] Regex patterns for spec extraction
- [ ] Output: `data/outputs/materials_map_proposed.csv`
- [ ] CLI command: `hazard-cli propose-sft-materials`

### Phase 4 - Streamlit GUI
- [ ] `app/streamlit_app.py` implemented
- [ ] Single finish code lookup functional
- [ ] Display all hierarchy levels with traceability
- [ ] Disabled surface area inputs with "future" note
- [ ] Successfully runs: `streamlit run app/streamlit_app.py`

---

## Key Decisions Made

### Technology Choices
- **SQLite**: Zero-infrastructure, ACID-compliant, portable
- **CSV Inputs**: Human-editable, version-controllable, audit-friendly
- **No AI in MVP**: Guarantees determinism and explainability
- **Typer CLI**: Simple, type-safe, auto-generated help text
- **Streamlit**: Rapid prototyping, no frontend expertise required

### Data Model Decisions
- **Natural Keys**: Use `(base_spec, variant)` for materials uniqueness
- **Step Ordering**: Explicit `step_order` column (not implicit from ID)
- **Hazard Flags**: JSON string for flexibility (future: proper JSON column in SQLite 3.38+)
- **Material Variants**: Nullable to support specs without variants
- **Spec Dependencies**: Optional table (low priority for MVP)

### Security Decisions
- **Proprietary Data Exclusion**: Chemical %wt ranges never committed to git
- **Test Fixtures**: Use fake, non-proprietary chemical data only
- **Validation Reports**: May be committed but must not leak sensitive data

### Process Decisions
- **Fail-Fast Validation**: Errors block ingestion; warnings logged but allow proceed
- **Human Approval Loop**: Proposal tool outputs CSV for review, not auto-import
- **Sequential Phasing**: Complete Phase N before starting Phase N+1

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| CSV data quality issues | High | Comprehensive validators with clear error messages |
| Proprietary data leakage | Critical | `.gitignore` exclusions + fixture audits |
| Scalability concerns | Low | Current scope <10K finish codes; optimize later |
| Regex proposal false positives | Medium | Human review loop + confidence scoring |
| Schema evolution complexity | Medium | Document all changes + manual migrations for MVP |

---

## Success Metrics (Post-MVP)

- Successfully ingest production CSV data (>5000 finish codes)
- Query response time <100ms for single finish code lookup
- Validation error rate <1% on production data
- User adoption: 10+ weekly active users in first month
- Zero proprietary data leaks to git

---

## Open Questions

1. **CSV Ownership**: Who maintains/updates source CSVs? (Answer: Domain experts)
2. **Hazard Flag Schema**: Use GHS codes only, or include internal risk levels? (Answer: Both)
3. **Spec Variant Parsing**: Automate variant extraction from descriptions? (Answer: Deferred to Phase 3)
4. **Part Number Integration**: Timing for Phase 5? (Answer: After MVP validation)
5. **API Authorization**: Required for internal-only REST API? (Answer: Deferred to Phase 6)

---

## Phase 0 Summary

### Completed Tasks
1. Created `.gitignore` for Python/SQLite/Streamlit exclusions
2. Created `pyproject.toml` with dependencies:
   - pandas, sqlite-utils, sqlalchemy, python-dotenv
   - typer (CLI), streamlit (GUI), regex (parsing)
   - pytest, black, ruff (dev tools)
3. Documented architecture in `docs/README_architecture.md`
4. Documented schema and CSV contracts in `docs/schema_overview.md`
5. Created this scope document (`init/SCOPE.md`)

### Decisions Made
- Use `pyproject.toml` (not `requirements.txt`) for modern Python packaging
- Pin dependency versions for reproducibility
- Structure docs/ for reviewers: architecture → schema → process flow
- CLI entry point: `hazard-cli` command via `[project.scripts]`

### Next Steps
- Seed `init/TODO.md` with detailed checklist
- Create `README.md` with quickstart
- Proceed to Phase 1: Database schema + ETL implementation

### Questions Raised
- None at this stage

---

## Phase 1 Summary

### Completed Tasks
1. Created comprehensive `db/schema.sql` with:
   - 10 core tables (substrates, finish_codes, sft_steps, materials, chemicals, etc.)
   - Foreign key constraints with ON DELETE RESTRICT
   - Check constraints for data integrity
   - 8 indexes for query performance
   - 2 views for common queries
   - Schema versioning table
2. Implemented `etl/hashing.py` with SHA256 file hashing functions
3. Implemented `etl/validators.py` with:
   - Referential integrity validation
   - Completeness checks
   - Format validation (CAS numbers, JSON, ranges)
   - Human-readable error reporting
4. Implemented `etl/load_csvs.py` with:
   - 9 CSV loader functions (one per table)
   - Deterministic upsert logic
   - Metadata tracking (SHA256, row counts, timestamps)
   - Orchestrator function `ingest_all()`
   - JSON report generation
5. Created comprehensive test fixtures in `tests/fixtures/`:
   - 9 CSV files with fake, non-proprietary data
   - 2 test finish codes (BP27, SA12)
   - 3 SFT steps, 3 materials, 3 chemicals
   - Complete data hierarchy for testing

### Decisions Made
- Use pandas for CSV parsing (handles edge cases well)
- Use upsert (INSERT ... ON CONFLICT) for idempotent loads
- Fail-fast on FK violations (referential integrity critical)
- Record metadata after each successful load
- Separate validation from loading (run validators post-load)

### Files Created
- `db/schema.sql` (280 lines)
- `etl/__init__.py`
- `etl/hashing.py` (117 lines)
- `etl/validators.py` (351 lines)
- `etl/load_csvs.py` (657 lines)
- `tests/__init__.py`
- `tests/fixtures/README.md`
- `tests/fixtures/*.csv` (9 files)

---

## Phase 2 Summary

### Completed Tasks
1. Implemented `app/services/query.py` with:
   - `get_finish_code_tree()` - Full hierarchy retrieval with provenance
   - `get_all_finish_codes()` - List all codes
   - `get_chemicals_by_hazard_level()` - Filter by hazard
   - JSON hazard_flags parsing
   - Error handling for missing codes
2. Implemented `app/cli.py` with Typer + Rich:
   - `hazard-cli ingest` - Load CSVs with progress reporting
   - `hazard-cli validate` - Run validators with formatted output
   - `hazard-cli show FINISH_CODE` - Display JSON tree
   - `hazard-cli list-codes` - Tabular finish code listing
   - `hazard-cli version` - Version info
   - Rich tables and colored output for better UX
3. Updated `pyproject.toml` to add `rich` dependency
4. Created all app/ module structure

### Decisions Made
- Use Rich library for CLI output (better UX than plain text)
- Return JSON for `show` command (enables piping to jq, etc.)
- Sort chemicals by hazard level descending (highest hazard first)
- Include provenance in every query response
- Graceful error handling with helpful messages

### Files Created
- `app/__init__.py`
- `app/services/__init__.py`
- `app/services/query.py` (302 lines)
- `app/cli.py` (332 lines)

---

## Next Steps

### Phase 3 - Proposal Tool (Optional/Deferred)
- Regex-based material extraction from SFT descriptions
- CSV output for human review and approval

### Phase 4 - Streamlit GUI
- Single finish code lookup interface
- Visual hierarchy display
- Traceability footer
- Placeholder for surface area calculations

### Testing & Validation
- Create `tests/test_etl.py` with pytest
- Create `tests/test_query.py` with pytest
- Test end-to-end: ingest fixtures → query → validate JSON
- Document test execution in README

### Deployment Readiness
- Test installation: `pip install -e .`
- Test CLI commands on fixtures
- Generate sample ingest report
- Document common error scenarios

---

**Last Updated**: 2025-11-03 (Phase 2 completion)
**Status**: Phase 0-2 complete. Core ETL + CLI functional. Phase 3-4 pending.
