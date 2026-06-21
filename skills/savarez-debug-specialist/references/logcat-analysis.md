# Logcat Analysis Reference

## Purpose

Parse and analyze Android logcat output for errors and warnings.

## Inputs

- Logcat text file or live logcat stream
- Filter: logcat buffer (main, system, crash, events)

## Detection Logic

### Error Count

```bash
LOGCAT_ERRORS=$(grep -c " E " logcat.txt 2>/dev/null)
```

### Warning Count

```bash
LOGCAT_WARNINGS=$(grep -c " W " logcat.txt 2>/dev/null)
```

### Fatal Errors

```bash
grep " F " logcat.txt 2>/dev/null | head -5
```

### App Crashes

```bash
grep -A5 "FATAL EXCEPTION" logcat.txt 2>/dev/null | head -20
```

### ANR Events

```bash
grep -A10 "ANR in" logcat.txt 2>/dev/null | head -20
```

## Output Format

- Error summary (count, categories)
- Top error patterns
- Crash stacktraces
- ANR reports

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | Stacktrace + exception type |
| MEDIUM | Error pattern matched |
| LOW | Generic error count |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Normal warnings | Filter by severity |
| Verbose logging | Filter by tag |
| Debug messages | Ignore debug level |
