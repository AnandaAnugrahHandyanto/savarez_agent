# Boot & Recovery Audit Reference

## Overview

Validates boot layout and recovery configuration.

---

## Boot Layout Detection

| Layout | Indicators |
|--------|------------|
| Legacy | boot.img only, no A/B |
| A/B | AB_OTA_PARTITIONS defined |
| Virtual A/B | AB_OTA + snapshot + merge |
| GKI | init_boot + vendor_boot |

---

## Boot Component Checks

| Check | Weight | Description |
|-------|--------|-------------|
| boot.img | 16.7% | Boot image present |
| init_boot.img | 16.7% | GKI init boot |
| vendor_boot.img | 16.7% | Vendor boot |
| recovery.fstab | 16.7% | Recovery fstab |
| init.recovery.rc | 16.7% | Recovery init |
| fastbootd | 8.3% | Fastbootd support |
| Dynamic partitions | 8.3% | Dynamic partition support |

---

## Scoring

| Check | Pass | Fail |
|-------|------|------|
| boot.img | +2 | 0 |
| init_boot.img | +2 | 0 |
| vendor_boot.img | +2 | 0 |
| recovery.fstab | +2 | 0 |
| init.recovery.rc | +2 | 0 |
| fastbootd | +1 | 0 |
| Dynamic partitions | +1 | 0 |
| **Total** | **12** | |

---

## Virtual A/B Detection

### Indicators

```bash
# Snapshot support
BOARD_USES_RECOVERY_UPDATE=yes
BOARD_PREBUILT_BOOTIMAGE=yes
SNAPSHOT_UPDATE=yes

# A/B support
AB_OTA_PARTITIONS=yes
```

### Improved Detection

```bash
HAS_SNAPSHOT=$(grep -q "BOARD_USES_RECOVERY_UPDATE\|BOARD_PREBUILT_BOOTIMAGE\|SNAPSHOT_UPDATE" BoardConfig.mk 2>/dev/null && echo "yes" || echo "no")
HAS_AB=$(grep -q "AB_OTA_PARTITIONS" BoardConfig.mk 2>/dev/null && echo "yes" || echo "no")

if [ "$HAS_SNAPSHOT" = "yes" ] && [ "$HAS_AB" = "yes" ]; then
    LAYOUT="Virtual A/B"
fi
```

---

## Example Output

```
=== Boot & Recovery Audit ===

Boot Layout: GKI

[✓] boot.img
[✓] init_boot.img
[✓] vendor_boot.img
[✓] recovery.fstab
[✓] init.recovery.rc
[✓] fastbootd
[✓] Dynamic partitions

Boot & Recovery: 12/12
```
