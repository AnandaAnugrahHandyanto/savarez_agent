# VTS Vendor Test Reference

## Purpose

Validate Vendor Test Suite compliance.

## Inputs

- VTS test results
- Vendor HAL versions
- Device configuration

## Detection Logic

### Parse VTS Results

```bash
# Count passes
grep -c "PASS" vts_results.xml

# Count failures
grep -c "FAIL" vts_results.xml

# Calculate pass rate
PASS_RATE=$((PASS * 100 / (PASS + FAIL)))
```

### Identify Failed HALs

```bash
# Extract failed HALs
grep "result=\"fail\"" vts_results.xml | grep -i "hal" | head -10

# Check HAL coverage
grep -c "test" vts_results.xml
```

## Output Format

- Total tests
- Pass/Fail counts
- HAL coverage
- Failed HALs list

## Validation Criteria

| Metric | Threshold | Status |
|--------|-----------|--------|
| Pass rate | ≥ 95% | PASS |
| Pass rate | 90-94% | WARNING |
| Pass rate | < 90% | FAIL |

## Scoring

| Pass Rate | Score |
|-----------|-------|
| ≥ 95% | 100 |
| 90-94% | 80 |
| 85-89% | 60 |
| < 85% | 40 |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Missing HALs | Check if required |
| Version mismatches | Verify vendor blobs |
| Platform differences | Check device config |
