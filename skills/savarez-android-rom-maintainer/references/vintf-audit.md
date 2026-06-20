# VINTF Audit Reference

## Overview

Validates VINTF manifest and compatibility matrix.

---

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| manifest.xml | 33.3% | Vendor manifest exists |
| compatibility_matrix.xml | 33.3% | Framework matrix exists |
| HAL count | 33.3% | Sufficient HALs declared |

---

## Scoring

| Check | Pass | Fail |
|-------|------|------|
| manifest.xml | +5 | 0 |
| compatibility_matrix.xml | +5 | 0 |
| HAL count >20 | +5 | 0 |
| **Total** | **15** | |

---

## Required HALs

| HAL | Description |
|-----|-------------|
| android.hardware.camera.provider | Camera |
| android.hardware.graphics.composer | Display |
| android.hardware.health | Battery |
| android.hardware.keymaster | Security |
| android.hardware.power | Power |

---

## Common Issues

| Issue | Impact | Fix |
|-------|--------|-----|
| Missing manifest | Build failure | Create manifest.xml |
| HAL mismatch | Boot failure | Update manifest |
| Missing matrix | Compatibility issue | Add matrix |

---

## Example Output

```
=== VINTF Audit ===

[✓] manifest.xml
[✓] compatibility_matrix.xml
[✓] HAL declarations: 47

VINTF: 15/15
```
