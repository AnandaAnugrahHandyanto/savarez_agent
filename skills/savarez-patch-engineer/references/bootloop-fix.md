# Bootloop Fix Recommendation Reference

## Purpose

Recommend fixes for boot loops.

## Inputs

- Bootloop logcat
- Crash analysis
- System state

## Detection Logic

### System Server Crash

```bash
grep "system_server.*crash\|system_server.*died" logcat.txt
```

### Watchdog Timeout

```bash
grep "Watchdog.*timeout" logcat.txt
```

### Boot Phase

```bash
grep "boot_progress" logcat.txt | tail -5
```

## Output Format

- Root cause: System server crash / watchdog
- Recommended change: Fix crash or increase timeout
- Affected files: frameworks/base/
- Example diff: Code fix suggestion
- Risk level: HIGH

## Risk Level Guidance

| Boot Phase | Risk |
|------------|------|
| Early boot (zygote) | CRITICAL |
| System server | HIGH |
| Late boot | MEDIUM |
| Boot completed | LOW |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Transient crash | Check repeat count |
| Memory pressure | Check memory |
| Deadlock | Check threads |
| Hardware issue | Verify hardware |
