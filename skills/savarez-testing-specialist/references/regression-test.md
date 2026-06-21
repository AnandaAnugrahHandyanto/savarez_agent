# Regression Test Manager Reference

## Purpose

Track test results across builds for regression detection.

## Inputs

- Current test results
- Previous test results
- Change log

## Detection Logic

### Compare Pass Rates

```bash
# Current pass count
CURRENT_PASS=$(grep -c "PASS" current_results.xml)

# Previous pass count
PREVIOUS_PASS=$(grep -c "PASS" previous_results.xml)

# Calculate regression
REGRESSION=$((PREVIOUS_PASS - CURRENT_PASS))
```

### Identify New Failures

```bash
# Find tests that passed before but fail now
diff previous_results.xml current_results.xml | grep "FAIL"

# Find tests that failed before but pass now
diff previous_results.xml current_results.xml | grep "PASS"
```

## Output Format

- Pass rate change
- New failures
- Fixed tests
- Regression status

## Validation Criteria

| Metric | Threshold | Status |
|--------|-----------|--------|
| Regression | 0 | PASS |
| Regression | 1-5 tests | WARNING |
| Regression | > 5 tests | FAIL |

## Scoring

| Regression | Score |
|------------|-------|
| 0 | 100 |
| 1-2 | 80 |
| 3-5 | 60 |
| > 5 | 40 |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Flaky tests | Run multiple iterations |
| Environment changes | Check test environment |
| Test updates | Check test version |
