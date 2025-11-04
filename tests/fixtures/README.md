# Test Fixtures

This directory contains **fake, non-proprietary test data** for validating the hazardous finishes ETL and query engine.

## Important Notes

- All chemical names, CAS numbers, and weight percentages are **fictional** or **public domain**
- No proprietary formulations are included
- Data is designed to test ETL logic, not represent real-world finish processes

## Test Scenario

### Finish Codes
- **BP27**: Brass Passivate, sequence 27
- **SA12**: Steel Anodize, sequence 12

### SFT Steps
- **SFT-DEGREASE**: Generic alkaline degrease step
- **SFT-PASSIVATE**: Generic passivation step
- **SFT-ANODIZE**: Generic anodizing step

### Materials
- **TEST-SPEC-001**: Fake cleaner spec
- **TEST-SPEC-002 TYPE A**: Fake anodize spec with variant
- **TEST-SPEC-003**: Fake sealant spec

### Chemicals
- **Water** (H2O, CAS 7732-18-5): Non-hazardous, baseline chemical
- **Test Acid A** (Fake CAS 99999-99-9): Simulated corrosive acid
- **Test Base B** (Fake CAS 88888-88-8): Simulated caustic base

## Data Relationships

```
BP27 (Brass Passivate)
  └─ SFT-DEGREASE (step 1)
      └─ TEST-SPEC-001
          ├─ Water (50-70%)
          └─ Test Base B (10-20%)
  └─ SFT-PASSIVATE (step 2)
      └─ TEST-SPEC-003
          └─ Test Acid A (5-15%)

SA12 (Steel Anodize)
  └─ SFT-ANODIZE (step 1)
      └─ TEST-SPEC-002 TYPE A
          ├─ Water (60-80%)
          └─ Test Acid A (10-20%)
```

## CSV Files

1. `substrates.csv` - 3 substrate types
2. `finish_applied.csv` - 3 finish types
3. `finish_codes.csv` - 2 finish codes
4. `sft_steps.csv` - 3 SFT steps
5. `finish_code_steps.csv` - 3 step assignments
6. `materials_map.csv` - 3 materials
7. `sft_material_links.csv` - 3 SFT-material links
8. `chemicals.csv` - 3 chemicals
9. `material_chemicals.csv` - 5 chemical compositions

## Usage

```python
from etl.load_csvs import ingest_all

report = ingest_all("tests/fixtures", "test_db.sqlite")
assert report["status"] == "success"
```
