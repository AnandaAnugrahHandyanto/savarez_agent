# Service Crash Analysis Reference

## Purpose

Analyze Android system service crashes.

## Inputs

- Logcat for service crashes
- System server logs
- Watchdog dumps

## Detection Logic

### System Server Crashes

```bash
logcat 2>/dev/null | grep "system_server.*crash\|system_server.*died" | head -5
```

### Service Failures

```bash
logcat 2>/dev/null | grep "ServiceManager.*fail" | head -10
```

### Watchdog Dumps

```bash
logcat 2>/dev/null | grep "Watchdog.*dump" | head -5
```

### Deadlocks

```bash
logcat 2>/dev/null | grep "deadlock\|blocked" | head -10
```

## Output Format

- Crashed service
- Crash reason
- Thread state
- Recommended fix

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | Service name + crash reason identified |
| PROBABLE | Service restart detected |
| POSSIBLE | Watchdog triggered |
| UNKNOWN | Insufficient service data |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Expected restarts | Check crash count |
| Thread contention | Check load |
| Memory pressure | Check memory |
