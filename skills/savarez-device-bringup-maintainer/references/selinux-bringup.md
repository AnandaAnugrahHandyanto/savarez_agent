# SELinux Bring-Up Audit Reference

## Purpose

Validate SELinux for bring-up.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| SELinux policy | 25% | Policy present |
| File contexts | 25% | File contexts |
| Property contexts | 25% | Property contexts |
| Service contexts | 25% | Service contexts |

## Detection Methods

### SELinux Policy

```bash
find device/ -name "sepolicy" -type d 2>/dev/null | head -1 | grep -q . && echo "[✓] SELinux policy"
```

### File Contexts

```bash
find device/ -name "file_contexts" 2>/dev/null | head -1 | grep -q . && echo "[✓] File contexts"
```

### Property Contexts

```bash
find device/ -name "property_contexts" 2>/dev/null | head -1 | grep -q . && echo "[✓] Property contexts"
```

### Service Contexts

```bash
find device/ -name "service_contexts" 2>/dev/null | head -1 | grep -q . && echo "[✓] Service contexts"
```

## Score

16 points max (4 checks × 4 points)

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Permissive mode | Report mode, not just presence |
| Generic policy | Check for device-specific |
| Context variants | Check file naming patterns |
