# Installation Guide

## Prerequisites

- Python 3.10 or higher
- pip or uv package manager

## Installation Steps

### 1. Install the package

```bash
# Using pip
pip install -e .

# Or using uv (faster)
uv pip install -e .
```

### 2. Verify installation

```bash
hazard-cli --help
```

You should see the CLI help with available commands.

### 3. Test with fixtures

```bash
# Ingest test data
hazard-cli ingest --input tests/fixtures

# List finish codes
hazard-cli list-codes

# Query a finish code
hazard-cli show BP27
```

## Troubleshooting

### No module named 'pip'

If you see this error when running `pip install`, you need to install pip:

```bash
# On Debian/Ubuntu
sudo apt install python3-pip

# Or use uv instead
curl -LsSf https://astral.sh/uv/install.sh | sh
uv pip install -e .
```

### Virtual environment creation fails

If `python3 -m venv .venv` fails:

```bash
# On Debian/Ubuntu
sudo apt install python3-venv

# Then create venv
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### ImportError after installation

Make sure you're in the virtual environment:

```bash
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

## Dependencies Installed

The following packages will be installed:

**Core:**
- pandas==2.2.0 - CSV parsing and data manipulation
- sqlite-utils==3.36 - SQLite utilities
- sqlalchemy==2.0.25 - Database ORM
- python-dotenv==1.0.1 - Environment variables

**CLI:**
- typer==0.9.0 - CLI framework
- rich==13.7.0 - Terminal formatting

**GUI (optional):**
- streamlit==1.31.0 - Web GUI framework

**Other:**
- regex==2023.12.25 - Advanced regex patterns

**Development (optional):**
- pytest==8.0.0 - Testing framework
- pytest-cov==4.1.0 - Code coverage
- black==24.1.1 - Code formatter
- ruff==0.2.0 - Linter

## Verifying Installation

Run the test script:

```bash
./test_installation.sh
```

This checks:
- Python version
- File encodings
- Python syntax
- Test fixtures
- Documentation
- Database schema

## Next Steps

After installation, see:
- `README.md` - User guide and CLI reference
- `docs/README_architecture.md` - System architecture
- `docs/schema_overview.md` - Database schema and CSV contracts
- `init/SCOPE.md` - Project scope and implementation status

## Getting Help

```bash
# General help
hazard-cli --help

# Command-specific help
hazard-cli ingest --help
hazard-cli validate --help
hazard-cli show --help
```

## Production Deployment

For production use:

1. Place your CSV files in `data/inputs/`
2. Run ingestion: `hazard-cli ingest`
3. Validate data: `hazard-cli validate`
4. Query codes: `hazard-cli show YOUR_CODE`

**Security Note:** Do not commit `data/inputs/*.csv` or `db/*.sqlite` to git. These contain proprietary chemical compositions.
