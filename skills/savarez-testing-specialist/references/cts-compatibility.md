# CTS Compatibility Test Reference

## Purpose

Validate Android Compatibility Test Suite compliance.

## Inputs

- CTS test results (XML/JSON)
- Device build info
- Android version

## Detection Logic

### Parse CTS Results

```bash
# Count passes
grep -c "PASS" cts_results.xml

# Count failures
grep -c "FAIL" cts_results.xml

# Calculate pass rate
PASS_RATE=$((PASS * 100 / (PASS + FAIL)))
```

### Identify Failed Modules

```bash
# Extract failed modules
grep "result=\"fail\"" cts_results.xml | head -10

# Group by module
grep "result=\"fail\"" cts_results.xml | awk -F'"' '{print $4}' | sort | uniq -c | sort -rn
```

## Output Format

- Total tests
- Pass count
- Fail count
- Pass rate
- Failed modules list

## Validation Criteria

| Metric | Threshold | Status |
|--------|-----------|--------|
| Pass rate | ≥ 98% | PASS |
| Pass rate | 95-97% | WARNING |
| Pass rate | < 95% | FAIL |

## Scoring

| Pass Rate | Score |
|-----------|-------|
| ≥ 98% | 100 |
| 95-97% | 80 |
| 90-94% | 60 |
| < 90% | 40 |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Environment issues | Check test environment |
| Device-specific failures | Compare with baseline |
| Flaky tests | Run multiple iterations |
