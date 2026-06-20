# Defconfig Audit Reference

## Purpose

Validate kernel defconfig configuration.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| defconfig exists | 25% | Device defconfig present |
| CONFIG_LOCALVERSION | 25% | Local version set |
| CONFIG_MODULES | 25% | Module support enabled |
| CONFIG_SMP | 25% | Symmetric multiprocessing |

## Scoring

| Check | Pass | Fail |
|-------|------|------|
| defconfig | +4 | 0 |
| LOCALVERSION | +4 | 0 |
| MODULES | +4 | 0 |
| SMP | +4 | 0 |
| **Total** | **16** | |

## Common Issues

| Issue | Impact | Fix |
|-------|--------|-----|
| Missing defconfig | Build failure | Create defconfig |
| No LOCALVERSION | Version issues | Add version |
| MODULES disabled | No module support | Enable MODULES |

## Example Output

```
=== Defconfig Audit ===

[✓] onyx_defconfig
[✓] CONFIG_LOCALVERSION
[✓] CONFIG_MODULES=y
[✓] CONFIG_SMP=y

Defconfig: 16/16
```
