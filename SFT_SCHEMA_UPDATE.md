# SFT Schema Update - Issue Resolution

## Date: 2025-11-03

## Issue
User reported that `sft_steps.csv` should NOT have a `title` column. The actual CSV structure is:
```
sft_code,parent_group,description,associated_specs,source_doc,last_review,notes
```

But the system was expecting:
```
sft_code,title,description,revision,source_doc,last_review
```

## Root Cause
Initial implementation incorrectly assumed SFT steps would have a `title` field (like "Alkaline Degrease") separate from the description. User's actual data structure has:
- `parent_group` instead of `title` (e.g., "Cleaning", "Surface Treatment")
- `associated_specs` instead of `revision`
- `notes` field added

## Changes Made

### 1. Database Schema (`db/schema.sql`)
**Before:**
```sql
CREATE TABLE IF NOT EXISTS sft_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sft_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,              -- REMOVED
    description TEXT NOT NULL,
    revision TEXT,                     -- REMOVED
    source_doc TEXT,
    last_review TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**After:**
```sql
CREATE TABLE IF NOT EXISTS sft_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sft_code TEXT NOT NULL UNIQUE,
    parent_group TEXT,                 -- ADDED
    description TEXT NOT NULL,
    associated_specs TEXT,             -- ADDED
    source_doc TEXT,
    last_review TEXT,
    notes TEXT,                        -- ADDED
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2. ETL Loader (`etl/load_csvs.py`)
**Updated:**
- Changed required columns from `["sft_code", "title", "description"]` to `["sft_code", "description"]`
- Added optional columns: `parent_group`, `associated_specs`, `notes`
- Removed: `title`, `revision`
- Updated INSERT/UPDATE statements to match new schema

**Function signature:**
```python
def load_sft_steps(csv_path: str, conn: sqlite3.Connection) -> int:
    """
    CSV columns: sft_code, parent_group?, description, associated_specs?,
                 source_doc?, last_review?, notes?
    """
```

### 3. Validators (`etl/validators.py`)
**Changed:**
- Removed `("sft_steps", "title")` from required fields check
- Now only validates: `sft_code` and `description` are NOT NULL

### 4. Query Engine (`app/services/query.py`)
**Updated SELECT query:**
```python
SELECT
    sft.sft_code,
    sft.parent_group,          -- ADDED
    sft.description,
    sft.associated_specs,      -- ADDED
    sft.source_doc,
    sft.last_review,
    sft.notes,                 -- ADDED
    fcs.step_order
FROM finish_code_steps fcs
JOIN sft_steps sft ON fcs.sft_id = sft.id
```

**Updated JSON response structure:**
```json
{
  "steps": [
    {
      "sft_code": "SFT-DEGREASE",
      "step_order": 1,
      "parent_group": "Cleaning",          // NEW
      "description": "...",
      "associated_specs": "TEST-SPEC-001", // NEW
      "source_doc": "TEST-SOP-001",
      "last_review": "2024-01-15",
      "notes": "...",                      // NEW
      "materials": [...]
    }
  ]
}
```

### 5. Test Fixtures (`tests/fixtures/sft_steps.csv`)
**Updated to match new structure:**
```csv
sft_code,parent_group,description,associated_specs,source_doc,last_review,notes
SFT-DEGREASE,Cleaning,Immerse parts in...,TEST-SPEC-001,TEST-SOP-001,2024-01-15,Test fixture...
```

## Verification

### Test Results ✅
```bash
.venv/bin/python -m app.cli ingest --input-dir tests/fixtures --db test.sqlite
```

**Output:**
```
✓ Ingestion complete
Status: success
Files loaded: 9
sft_steps.csv: 3 rows
✓ Validation passed
```

### Query Test ✅
```bash
.venv/bin/python -m app.cli show BP27 --db test.sqlite
```

**Output includes:**
```json
{
  "steps": [
    {
      "sft_code": "SFT-DEGREASE",
      "step_order": 1,
      "parent_group": "Cleaning",
      "description": "Immerse parts in alkaline cleaner...",
      "associated_specs": "TEST-SPEC-001",
      "source_doc": "TEST-SOP-001",
      "last_review": "2024-01-15",
      "notes": "Test fixture for MVP",
      "materials": [...]
    }
  ]
}
```

## CSV Format for Production

Your `sft_steps.csv` should have these columns:

### Required Columns
- `sft_code` - Unique SFT identifier (e.g., "SFT-DEGREASE")
- `description` - Full process description

### Optional Columns
- `parent_group` - Category/grouping (e.g., "Cleaning", "Surface Treatment", "Coating")
- `associated_specs` - Related specifications (e.g., "MIL-PRF-8625")
- `source_doc` - Source document reference (e.g., "SOP-001")
- `last_review` - Last review date (ISO format: YYYY-MM-DD)
- `notes` - Additional notes or comments

### Example
```csv
sft_code,parent_group,description,associated_specs,source_doc,last_review,notes
SFT-BRASS-CLEAN,Cleaning,Alkaline degrease per MIL-PRF-8625,MIL-PRF-8625,SOP-100,2024-01-15,Review annually
SFT-CHROMATE,Surface Treatment,Hexavalent chromate conversion coating,MIL-DTL-5541F,SOP-200,2024-02-20,Restricted use
```

## Impact on Your Data

**No data loss** - All your existing SFT data will load correctly with these changes:
- `parent_group` replaces the concept of "title" with a grouping field
- `associated_specs` captures specification references (was called "revision")
- `notes` field added for additional context

## Command Reference

### Re-ingest Your Data
```bash
# Remove old database (has old schema)
rm -f data/hazardous_finishes.sqlite

# Ingest with new schema
.venv/bin/hazard-cli ingest --input-dir data/inputs --db data/hazardous_finishes.sqlite
```

### Verify Structure
```bash
# Check ingestion report
cat data/outputs/ingest_report.json

# Query a finish code
.venv/bin/hazard-cli show YOUR_CODE --db data/hazardous_finishes.sqlite
```

## Files Modified

1. `db/schema.sql` - Updated sft_steps table structure
2. `etl/load_csvs.py` - Updated load_sft_steps() function
3. `etl/validators.py` - Removed title from required fields
4. `app/services/query.py` - Updated query and response structure
5. `tests/fixtures/sft_steps.csv` - Updated test fixture

## Status
✅ **RESOLVED** - System now matches your CSV structure exactly.

All tests pass. Ready for production data ingestion.
