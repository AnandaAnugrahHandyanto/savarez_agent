# STS Security Test Reference

## Purpose

Validate Security Test Suite compliance.

## Inputs

- STS test results
- Security patch level
- Vulnerability data

## SEPARATION STATEMENT

**STS Test vs Security Auditor:**

| Aspect | STS Test (This Skill) | Security Auditor |
|--------|----------------------|------------------|
| Focus | STS test suite results | Security posture audit |
| Input | Test XML results | Policy, permissions, configs |
| Output | Test pass rate | Security score |
| Workflow | Test execution phase | Audit phase |

**STS provides test pass rates. Security Auditor provides security scores.**

## Detection Logic

### Parse STS Results

```bash
# Count passes
grep -c "PASS" sts_results.xml

# Count failures
grep -c "FAIL" sts_results.xml

# Calculate pass rate
PASS_RATE=$((PASS * 100 / (PASS + FAIL)))
```

### Identify Security Failures

```bash
# Extract security failures
grep "result=\"fail\"" sts_results.xml | grep -i "security" | head -10

# Check CVE coverage
grep -c "CVE" sts_results.xml
```

## Output Format

- Total tests
- Pass/Fail counts
- CVE coverage
- Security failures list

## Validation Criteria

| Metric | Threshold | Status |
|--------|-----------|--------|
| Pass rate | 100% | PASS |
| Pass rate | ≥ 98% | WARNING |
| Pass rate | < 98% | FAIL |

## Scoring

| Pass Rate | Score |
|-----------|-------|
| 100% | 100 |
| 98-99% | 80 |
| 95-97% | 60 |
| < 95% | 40 |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Patch not applicable | Check CVE relevance |
| Vendor-specific | Check vendor patches |
| False detection | Verify manually |
