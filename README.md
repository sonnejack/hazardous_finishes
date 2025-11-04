# Hazardous Finishes Data Engine

A deterministic data engine for mapping Finish Codes to SFT Steps to Materials to Chemicals with hazard tracking and traceability.

## Purpose

This system enables:
- Lookup of finish codes (e.g., "BP27") to retrieve complete hierarchies
- Compliance tracking of carcinogens, corrosives, and other GHS-classified hazards
- Traceability of data lineage via CSV version tracking (SHA256)
- Human-readable validation reports for data quality

**Key Principle**: No AI in core flows. All mappings are human-curated via CSV inputs.

## Quick Start

### Installation

```bash
# Clone repository
cd hazardous_finishes

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Verify installation
hazard-cli --help
```

### Prepare Data

Place your CSV files in `data/inputs/`:
- substrates.csv
- finish_applied.csv
- finish_codes.csv
- sft_steps.csv
- finish_code_steps.csv
- materials_map.csv
- sft_material_links.csv
- chemicals.csv
- material_chemicals.csv

See `docs/schema_overview.md` for CSV format specifications.

### Ingest Data

```bash
# Load CSVs into SQLite database
hazard-cli ingest --input data/inputs

# Validate referential integrity
hazard-cli validate

# Check ingestion report
cat data/outputs/ingest_report.json
```

### Query Finish Codes

```bash
# Display full hierarchy as JSON
hazard-cli show BP27

# List all finish codes
hazard-cli list-codes
```

## CLI Commands

### hazard-cli ingest

Load CSV files into SQLite database.

Options:
- `--input DIR` : Directory containing CSV files (default: `data/inputs`)
- `--db PATH` : Database path (default: `db/engine.sqlite`)

Example:
```bash
hazard-cli ingest --input data/inputs --db db/engine.sqlite
```

### hazard-cli validate

Run referential integrity and completeness checks.

Options:
- `--db PATH` : Database path (default: `db/engine.sqlite`)

Example:
```bash
hazard-cli validate
```

### hazard-cli show FINISH_CODE

Display full finish code hierarchy as JSON.

Arguments:
- `FINISH_CODE` : Finish code to query (e.g., "BP27")

Options:
- `--db PATH` : Database path (default: `db/engine.sqlite`)
- `--output FILE` : Write to JSON file instead of stdout

Example:
```bash
hazard-cli show BP27
hazard-cli show BP27 --output output.json
```

### hazard-cli list-codes

List all finish codes in database.

Example:
```bash
hazard-cli list-codes
```

## Project Structure

```
hazardous_finishes/
├── app/                    Application layer
│   ├── cli.py             Typer CLI commands
│   ├── streamlit_app.py   Streamlit GUI
│   └── services/          Business logic
│       └── query.py       Query engine
├── etl/                    ETL layer
│   ├── load_csvs.py       CSV ingestion orchestrator
│   ├── validators.py      Referential integrity checks
│   └── hashing.py         SHA256 file hashing
├── db/
│   ├── schema.sql         SQLite DDL
│   └── engine.sqlite      Runtime database (not in git)
├── data/
│   ├── inputs/            Source CSV files (not in git)
│   └── outputs/           Validation reports
├── docs/
│   ├── README_architecture.md  Architecture overview
│   ├── schema_overview.md      ERD and CSV contracts
│   └── process_flow.md         Process DFD
├── tests/
│   └── fixtures/          Test CSV files (fake data)
├── .gitignore
├── pyproject.toml
└── README.md
```

## Key Features

### Deterministic Processing
- No AI or machine learning in core data pipeline
- Regex-based proposal tool suggests material links (human approval required)
- Reproducible results with SHA256-tracked inputs

### Data Traceability
- Every query response includes CSV SHA256 hashes
- Ingestion timestamps recorded in database
- Validation reports provide audit trail

### Fail-Fast Validation
- Referential integrity checks (foreign keys)
- Orphan detection (dangling references)
- Format validation (CAS numbers, JSON hazard flags)
- Range validation (0-100% weight, 1-5 hazard levels)

### Hazard Classification
- GHS hazard codes (H350, H314, etc.)
- Hazard categories (CARCINOGEN, CORROSIVE, etc.)
- Severity levels (1=low, 5=extreme)
- Weight percentage ranges per chemical

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov=etl tests/

# Test with fixtures
hazard-cli ingest --input tests/fixtures --db test.sqlite
hazard-cli show BP27 --db test.sqlite
```

Test fixtures use fake, non-proprietary data only.

## Troubleshooting

### Installation Issues

Problem: `pip install -e .` fails with dependency conflicts

Solution: Use specific Python version:
```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### Ingestion Errors

Problem: `Foreign key constraint failed` during ingest

Solution: Check CSV order. Load parent tables before child tables.

Problem: `Duplicate code` error

Solution: Ensure `code` columns are unique in source CSVs.

### Query Issues

Problem: `Finish code not found`

Solution: Verify code exists in database:
```bash
sqlite3 db/engine.sqlite "SELECT * FROM finish_codes WHERE code = 'BP27';"
```

## Security

- **Proprietary Data**: Chemical weight percentages are confidential. Do not commit to git.
- **Test Fixtures**: Use fake data only.
- **SQL Injection**: All queries use parameterized statements.

## Documentation

- [Architecture Overview](docs/README_architecture.md)
- [Database Schema + CSV Contracts](docs/schema_overview.md)
- [Process Flow](docs/process_flow.md)
- [Scope & Decisions](init/SCOPE.md)
- [Implementation Checklist](init/TODO.md)

## License

Proprietary - Internal Use Only

---

Version: 0.1.0
Last Updated: 2025-11-03
Status: Phase 0-2 complete. Core ETL + CLI functional.
