#!/bin/bash
# Installation verification script for hazardous_finishes

set -e  # Exit on error

echo "========================================="
echo "Hazardous Finishes - Installation Test"
echo "========================================="
echo ""

# Check Python version
echo "1. Checking Python version..."
python3 --version
echo "✓ Python detected"
echo ""

# Check if README is clean UTF-8
echo "2. Checking README.md encoding..."
if file README.md | grep -q "UTF-8"; then
    echo "✓ README.md is clean UTF-8"
else
    echo "✗ README.md encoding issue"
    exit 1
fi
echo ""

# Compile all Python files
echo "3. Checking Python syntax..."
python3 -m py_compile etl/*.py app/*.py app/services/*.py
echo "✓ All Python files compile successfully"
echo ""

# Verify test fixtures exist
echo "4. Checking test fixtures..."
fixture_count=$(ls tests/fixtures/*.csv 2>/dev/null | wc -l)
if [ "$fixture_count" -eq 9 ]; then
    echo "✓ All 9 CSV test fixtures present"
else
    echo "✗ Expected 9 CSV fixtures, found $fixture_count"
    exit 1
fi
echo ""

# Verify documentation files
echo "5. Checking documentation..."
docs=("README.md" "docs/README_architecture.md" "docs/schema_overview.md"
      "docs/process_flow.md" "init/SCOPE.md" "init/TODO.md")
for doc in "${docs[@]}"; do
    if [ -f "$doc" ]; then
        echo "  ✓ $doc"
    else
        echo "  ✗ $doc missing"
        exit 1
    fi
done
echo ""

# Verify database schema
echo "6. Checking database schema..."
if [ -f "db/schema.sql" ]; then
    table_count=$(grep -c "CREATE TABLE" db/schema.sql)
    echo "✓ Schema file exists with $table_count tables"
else
    echo "✗ db/schema.sql missing"
    exit 1
fi
echo ""

echo "========================================="
echo "✓ All pre-installation checks passed!"
echo "========================================="
echo ""
echo "Ready to install. Run:"
echo "  pip install -e ."
echo ""
echo "Then test with:"
echo "  hazard-cli --help"
echo "  hazard-cli ingest --input tests/fixtures"
echo "  hazard-cli show BP27"
