# Build Failure Root-Cause Reference

## Purpose

Analyze build failures for root cause.

## Inputs

- Build log (make.log, build.log)
- Error output
- Dependency info

## Detection Logic

### Error Summary

```bash
grep -i "error:" build.log 2>/dev/null | head -20
```

### Missing Files

```bash
grep -i "no such file\|not found" build.log 2>/dev/null | head -10
```

### Compilation Errors

```bash
grep -i "compilation error\|syntax error" build.log 2>/dev/null | head -10
```

### Linker Errors

```bash
grep -i "undefined reference\|ld returned" build.log 2>/dev/null | head -10
```

## Output Format

- Error type
- File/line location
- Missing dependency
- Recommended fix

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | Error type + file location identified |
| PROBABLE | Error pattern identified |
| POSSIBLE | Generic error detected |
| UNKNOWN | Insufficient build log |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Cascading errors | Check first error |
| Warning noise | Filter by severity |
| Stale build | Check clean build |
