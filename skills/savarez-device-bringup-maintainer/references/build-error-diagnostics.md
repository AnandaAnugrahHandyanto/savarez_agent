# Build Error Diagnostics Reference

## Purpose

Detect common build errors. Informational only — not scored.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Ninja failures | 12.5% | Ninja error patterns |
| Soong failures | 12.5% | Soong error patterns |
| Missing dependencies | 12.5% | Dependency errors |
| Missing blobs | 12.5% | Proprietary errors |
| Duplicate modules | 12.5% | Module conflicts |
| Namespace conflicts | 12.5% | Namespace errors |
| VINTF errors | 12.5% | VINTF manifest errors |
| SEPolicy errors | 12.5% | Policy errors |

## Detection Methods

### Ninja Failures

```bash
grep -r "ninja:" out/ 2>/dev/null | head -1 | grep -q . && echo "[!] Ninja failures"
```

### Soong Failures

```bash
grep -r "FAILED:" out/ 2>/dev/null | head -1 | grep -q . && echo "[!] Soong failures"
```

### Missing Dependencies

```bash
grep -r "missing:" out/ 2>/dev/null | head -1 | grep -q . && echo "[!] Missing dependencies"
```

### Missing Blobs

```bash
grep -r "proprietary" out/ 2>/dev/null | grep -q "missing\|not found" && echo "[!] Missing blobs"
```

### Duplicate Modules

```bash
grep -r "duplicate module" out/ 2>/dev/null | head -1 | grep -q . && echo "[!] Duplicate modules"
```

### Namespace Conflicts

```bash
grep -r "namespace" out/ 2>/dev/null | grep -q "conflict\|error" && echo "[!] Namespace conflicts"
```

### VINTF Errors

```bash
grep -r "vintf" out/ 2>/dev/null | grep -q "error\|fail" && echo "[!] VINTF errors"
```

### SEPolicy Errors

```bash
grep -r "checkpolicy\|sepolicy" out/ 2>/dev/null | grep -q "error\|fail" && echo "[!] SEPolicy errors"
```

## Score

Not scored (informational only)

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Stale out/ | Check timestamps |
| Partial builds | Require clean log |
| Generic errors | Filter critical only |
