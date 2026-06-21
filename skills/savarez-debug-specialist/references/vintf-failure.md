# VINTF Failure Analysis Reference

## Purpose

Analyze VINTF manifest and compatibility matrix errors.

## Inputs

- manifest.xml
- compatibility_matrix.xml
- VINTF errors from logcat

## Detection Logic

### VINTF Errors

```bash
logcat 2>/dev/null | grep -i "vintf\|hwbinder" | grep -i "error\|fail" | head -20
```

### Missing HALs

```bash
grep "hal" manifest.xml 2>/dev/null | head -20
```

### Version Mismatches

```bash
grep "version" manifest.xml compatibility_matrix.xml 2>/dev/null
```

## Output Format

- Missing HALs
- Version mismatches
- Interface errors
- Recommended fix

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | Missing HAL identified in manifest |
| PROBABLE | Version mismatch detected |
| POSSIBLE | VINTF error pattern |
| UNKNOWN | Insufficient VINTF data |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Optional HALs | Check required |
| Legacy HALs | Check version |
| AIDL vs HIDL | Check interface type |
