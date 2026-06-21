# HAL Failure Analysis Reference

## Purpose

Analyze HAL service crashes and failures.

## Inputs

- Logcat for HAL crashes
- HAL service status
- Tombstones for native crashes

## Detection Logic

### HAL Crashes

```bash
logcat 2>/dev/null | grep -i "hal.*crash\|hal.*died\|service.*died" | head -10
```

### Service Restarts

```bash
logcat 2>/dev/null | grep "ServiceManager.*restart" | head -10
```

### Binder Errors

```bash
logcat 2>/dev/null | grep "binder.*error\|binder.*fail" | head -10
```

## Output Format

- Crashed HAL service
- Crash reason
- Restart count
- Recommended fix

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | HAL crash with service name |
| PROBABLE | Service restart pattern |
| POSSIBLE | Binder error detected |
| UNKNOWN | Insufficient HAL data |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Expected restarts | Check crash count |
| Binder timeouts | Check load |
| Service updates | Check version |
