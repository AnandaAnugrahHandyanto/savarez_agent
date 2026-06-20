# SELinux Audit Reference

## Overview

Validates SELinux policy configuration for Android ROM.

---

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| sepolicy/ directory | 37.5% | Policy directory exists |
| Permissive domains | 37.5% | No permissive domains |
| file_contexts | 25% | File contexts defined |

---

## Scoring

| Check | Pass | Fail |
|-------|------|------|
| sepolicy/ exists | +3 | 0 |
| No permissive | +3 | 0 |
| file_contexts | +2 | 0 |
| **Total** | **8** | |

---

## Detection Logic

### Permissive Domains

```bash
PERMISSIVE=$(grep -r "permissive" sepolicy/ 2>/dev/null | grep -v "^#" | wc -l)
```

**Note:** Excludes comments (`#`).

### Common Issues

| Issue | Impact | Fix |
|-------|--------|-----|
| Permissive domain | Security risk | Remove permissive |
| Missing file_contexts | Boot failure | Add file_contexts |
| Missing device.te | Policy incomplete | Add device policy |

---

## Example Output

```
=== SELinux Audit ===

[✓] sepolicy/ exists
[✓] No permissive domains
[✓] file_contexts

SELinux: 8/8
```
