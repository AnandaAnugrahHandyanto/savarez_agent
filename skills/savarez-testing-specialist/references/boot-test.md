# Boot Test Validator Reference

## Purpose

Validate boot success and timing.

## Inputs

- Boot logs
- Boot timing data
- Boot failure logs

## Detection Logic

### Check Boot Success

```bash
# Check for boot completion
grep -i "boot completed" boot.log | tail -1

# Check for boot failures
grep -i "boot.*fail\|boot.*error" boot.log | wc -l
```

### Measure Boot Time

```bash
# Extract boot progress markers
grep -i "boot_progress" boot.log | tail -5

# Calculate total boot time
START=$(grep "boot_progress_start" boot.log | head -1 | awk '{print $2}')
END=$(grep "boot_progress_enable_screen" boot.log | tail -1 | awk '{print $2}')
BOOT_TIME=$(( (END - START) / 1000 ))
```

## Output Format

- Boot success/failure
- Boot time (seconds)
- Boot phase failures
- Boot test status

## Validation Criteria

| Metric | Threshold | Status |
|--------|-----------|--------|
| Boot success | 100% | PASS |
| Boot time | < 60s | PASS |
| Boot time | 60-90s | WARNING |
| Boot time | > 90s | FAIL |

## Scoring

| Metric | Score |
|--------|-------|
| Boot success + time < 60s | 100 |
| Boot success + time 60-90s | 80 |
| Boot success + time > 90s | 60 |
| Boot failure | 0 |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| First boot | Allow extra time |
| Cold boot | Check boot type |
| Device-specific | Check device baseline |
