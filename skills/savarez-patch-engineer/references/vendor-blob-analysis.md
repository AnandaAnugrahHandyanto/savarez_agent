# Vendor Blob Dependency Analysis Reference

## Purpose

Analyze vendor blob dependencies.

## Inputs

- proprietary-files.txt
- Missing blob errors
- Dependency graph

## Detection Logic

### Missing Blobs

```bash
grep -i "proprietary.*missing\|blob.*not found" build.log
```

### Dependencies

```bash
grep -i "depends\|requires" proprietary-files.txt
```

### Version Check

```bash
grep -i "version\|api" proprietary-files.txt
```

## Output Format

- Root cause: Missing vendor blob
- Recommended change: Add blob to proprietary-files.txt
- Affected files: vendor/*/proprietary-files.txt
- Example diff:
```diff
+vendor/lib64/libcamera.so
+vendor/lib64/libcamera_client.so
```
- Risk level: HIGH

## Risk Level Guidance

| Issue Type | Risk |
|------------|------|
| Add optional blob | LOW |
| Add required blob | HIGH |
| Version update | HIGH |
| Blob removal | CRITICAL |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Optional blob | Check if required |
| Version mismatch | Check API level |
| Missing dependency | Check dependency chain |
