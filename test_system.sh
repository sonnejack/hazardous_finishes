#!/bin/bash
# End-to-end system test

set -e

echo "======================================"
echo "Hazardous Finishes - System Test"
echo "======================================"
echo ""

# Activate venv
source .venv/bin/activate

# Test 1: Ingest fixtures
echo "Test 1: Ingesting test fixtures..."
python -m app.cli ingest --input-dir tests/fixtures --db test.sqlite > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ Ingest successful"
else
    echo "✗ Ingest failed"
    exit 1
fi

# Test 2: Validate database
echo "Test 2: Validating database..."
python -m app.cli validate --db test.sqlite > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ Validation passed"
else
    echo "✗ Validation failed"
    exit 1
fi

# Test 3: Query finish code
echo "Test 3: Querying finish code BP27..."
python -m app.cli show BP27 --db test.sqlite --output test_output.json 2>&1 | grep -q "✓"
if [ $? -eq 0 ]; then
    echo "✓ Query successful"
else
    echo "✗ Query failed"
    exit 1
fi

# Test 4: List codes
echo "Test 4: Listing all codes..."
python -m app.cli list-codes --db test.sqlite 2>&1 | grep -q "BP27"
if [ $? -eq 0 ]; then
    echo "✓ List codes successful"
else
    echo "✗ List codes failed"
    exit 1
fi

# Cleanup
rm -f test.sqlite test_output.json

echo ""
echo "======================================"
echo "✓ All system tests passed!"
echo "======================================"
echo ""
echo "System is ready for production use."
echo ""
echo "Next steps:"
echo "  1. Place your CSV files in data/inputs/"
echo "  2. Run: python -m app.cli ingest"
echo "  3. Query: python -m app.cli show YOUR_CODE"
