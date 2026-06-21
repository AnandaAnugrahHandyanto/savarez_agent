# Stability Test Runner Reference

## Purpose

Validate system stability under stress.

## Inputs

- Stability test results (Monkey, stress test)
- Duration
- Crash logs

## Detection Logic

### Parse Stability Results

```bash
# Count crashes
grep -c "CRASH" stability_results.txt

# Count ANRs
grep -c "ANR" stability_results.txt

# Calculate stability score
TOTAL_HOURS=24
CRASHES=$(grep -c "CRASH" stability_results.txt)
STABILITY=$(( (TOTAL_HOURS * 3600 - CRASHES * 60) * 100 / (TOTAL_HOURS * 3600) ))
```

### Analyze Crash Patterns

```bash
# Extract crash types
grep "CRASH" stability_results.txt | awk -F':' '{print $2}' | sort | uniq -c | sort -rn

# Check crash frequency
grep "CRASH" stability_results.txt | awk '{print $1}' | sort | uniq -c
```

## Output Format

- Test duration
- Crash count
- ANR count
- Stability score

## Validation Criteria

| Metric | Threshold | Status |
|--------|-----------|--------|
| Crashes | 0 | PASS |
| Crashes | 1-3 | WARNING |
| Crashes | > 3 | FAIL |

## Scoring

| Crashes | Score |
|---------|-------|
| 0 | 100 |
| 1-2 | 80 |
| 3-5 | 60 |
| > 5 | 40 |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Test duration | Check test length |
| Memory pressure | Check memory usage |
| Known issues | Check bug database |
