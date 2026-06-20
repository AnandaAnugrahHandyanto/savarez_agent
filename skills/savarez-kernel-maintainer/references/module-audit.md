# Module Audit Reference

## Purpose

Validate kernel module configuration.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| drivers/ directory | 25% | Drivers present |
| CONFIG_MODULE | 25% | Module support enabled |
| Key modules | 25% | Essential modules defined |
| Module signing | 25% | Module signing configured |

## Scoring

| Check | Pass | Fail |
|-------|------|------|
| drivers/ | +3 | 0 |
| MODULE | +3 | 0 |
| Modules | +3 | 0 |
| Signing | +3 | 0 |
| **Total** | **12** | |

## Common Issues

| Issue | Impact | Fix |
|-------|--------|-----|
| MODULES disabled | No module support | Enable MODULES |
| No module signing | Security risk | Enable signing |
| Missing drivers | Build failure | Add drivers |

## Example Output

```
=== Module Audit ===

[✓] drivers/ directory
[✓] CONFIG_MODULE=y
[✓] CONFIG_MODULES=y
[✓] Module signing

Module: 12/12
```
