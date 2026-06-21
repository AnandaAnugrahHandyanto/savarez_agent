# HAL Fix Recommendation Reference

## Purpose

Recommend fixes for HAL failures.

## Inputs

- HAL crash log
- Tombstone
- Service status

## Detection Logic

### Identify Crashed HAL

```bash
grep "hal.*crash\|service.*died" logcat.txt | head -1
```

### Check Tombstone

```bash
grep "signal\|fault addr" tombstone.txt | head -5
```

### Analyze Backtrace

```bash
grep -A20 "backtrace:" tombstone.txt | head -20
```

## Output Format

- Root cause: HAL crash (signal, address)
- Recommended change: Fix null pointer / memory leak
- Affected files: hardware/*/
- Example diff: Code fix suggestion
- Risk level: HIGH

## Risk Level Guidance

| Crash Type | Risk |
|------------|------|
| Null pointer | MEDIUM |
| Memory leak | HIGH |
| Use-after-free | CRITICAL |
| Double-free | CRITICAL |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Transient crash | Check repeat count |
| Memory issue | Check for leak |
| Hardware issue | Verify hardware |
| Race condition | Check threading |
