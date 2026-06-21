# Bootloop Diagnostics Reference

## Purpose

Identify root cause of boot loops.

## Inputs

- Logcat from boot attempts
- Kernel log
- Last known good state

## Detection Logic

### Boot Completion Check

```bash
logcat 2>/dev/null | grep "sys.boot_completed" | tail -1
```

### System Server Restarts

```bash
logcat 2>/dev/null | grep "system_server.*restart\|Zygote.*died" | head -5
```

### Boot Phase Failures

```bash
logcat 2>/dev/null | grep "boot_progress" | tail -5
```

### Watchdog Triggers

```bash
logcat 2>/dev/null | grep "Watchdog.*timeout" | head -5
```

## Output Format

- Boot phase where failure occurs
- Component causing restart
- Watchdog timeout info
- Recommended fix

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | Clear crash at specific boot phase |
| PROBABLE | Restart pattern identified |
| POSSIBLE | Multiple failure points |
| UNKNOWN | Insufficient boot log |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Transient failures | Check pattern |
| First boot delays | Allow extra time |
| Normal restarts | Filter by phase |
