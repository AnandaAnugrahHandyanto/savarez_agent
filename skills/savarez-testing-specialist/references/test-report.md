# Test Report Generator Reference

## Purpose

Generate comprehensive test report from all test results.

## Inputs

- All test results
- Pass/Fail data
- Performance metrics

## Detection Logic

### Aggregate Results

```bash
# Count total tests
TOTAL_TESTS=$(grep -c "test" *_results.xml)

# Count passes
TOTAL_PASS=$(grep -c "PASS" *_results.xml)

# Count failures
TOTAL_FAIL=$(grep -c "FAIL" *_results.xml)

# Calculate overall pass rate
OVERALL_PASS=$((TOTAL_PASS * 100 / TOTAL_TESTS))
```

### Generate Report

```bash
# Create summary
echo "=== Test Report ==="
echo "Total tests: $TOTAL_TESTS"
echo "Pass: $TOTAL_PASS"
echo "Fail: $TOTAL_FAIL"
echo "Pass rate: $OVERALL_PASS%"
```

## Output Format

- Test summary
- Pass/Fail rates
- Category breakdown
- Recommendations

## Scoring Model

```
Test Score = (
    CTS Score * 0.20 +
    VTS Score * 0.15 +
    STS Score * 0.15 +
    Functional Score * 0.15 +
    Regression Score * 0.10 +
    Performance Score * 0.10 +
    Stability Score * 0.05 +
    Boot Score * 0.05 +
    Hardware Score * 0.05
)
```

## Test Categories

| Score | Category |
|-------|----------|
| 95-100 | EXCELLENT |
| 85-94 | GOOD |
| 70-84 | ACCEPTABLE |
| 50-69 | POOR |
| 0-49 | FAILING |

## Example Report

```
=== Test Report ===

Device: Poco F7 (onyx)
Build: lineage-onyx-userdebug

=== Test Results ===
CTS: 99.0% (PASS)
VTS: 96.5% (PASS)
STS: 100% (PASS)
Functional: 97.5% (PASS)
Regression: 0 (PASS)
Performance: +2% (PASS)
Stability: 0 crashes (PASS)
Boot: 100% (PASS)
Hardware: 98.0% (PASS)

=== Overall Score: 97.8/100 ===
Category: EXCELLENT

=== Status: READY FOR RELEASE ===
```

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Weighting too aggressive | Adjust weights if needed |
| Category thresholds | Adjust based on testing |
| Missing data | Handle gracefully |
