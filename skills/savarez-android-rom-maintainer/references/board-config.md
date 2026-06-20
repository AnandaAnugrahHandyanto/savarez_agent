# Board Configuration Audit Reference

## Overview

Validates BoardConfig.mk and related configurations.

---

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| TARGET_KERNEL_SOURCE | 14.3% | Kernel source path |
| TARGET_KERNEL_CONFIG | 14.3% | Kernel config |
| TARGET_ARCH | 14.3% | Architecture |
| SYSTEM_PARTITION | 14.3% | System partition size |
| SUPER_PARTITION | 14.3% | Super partition size |
| PARTITION_GROUPS | 14.3% | Dynamic partition groups |
| AVB_ENABLE | 7.1% | AVB enabled |
| AVB_ROLLBACK | 7.1% | Rollback index |

---

## Scoring

| Check | Pass | Fail |
|-------|------|------|
| TARGET_KERNEL_SOURCE | +2 | 0 |
| TARGET_KERNEL_CONFIG | +2 | 0 |
| TARGET_ARCH | +2 | 0 |
| SYSTEM_PARTITION | +2 | 0 |
| SUPER_PARTITION | +2 | 0 |
| PARTITION_GROUPS | +2 | 0 |
| AVB_ENABLE | +1 | 0 |
| AVB_ROLLBACK | +1 | 0 |
| **Total** | **14** | |

---

## Dynamic Partitions

### Required

| Variable | Description |
|----------|-------------|
| BOARD_SUPER_PARTITION_SIZE | Super partition size |
| BOARD_SUPER_PARTITION_GROUPS | Partition groups |

### Optional

| Variable | Description |
|----------|-------------|
| BOARD_RETROFIT_DYNAMIC_PARTITIONS | Retrofit support |

---

## AVB Configuration

### Required

| Variable | Description |
|----------|-------------|
| BOARD_AVB_ENABLE | Enable AVB |

### Optional

| Variable | Description |
|----------|-------------|
| BOARD_AVB_ROLLBACK_INDEX | Rollback index |
| BOARD_AVB_KEY_PATH | Key path |

---

## Example Output

```
=== Board Configuration Audit ===

[✓] TARGET_KERNEL_SOURCE
[✓] TARGET_KERNEL_CONFIG
[✓] TARGET_ARCH
[✓] SYSTEM_PARTITION
[✓] SUPER_PARTITION
[✓] PARTITION_GROUPS
[✓] AVB_ENABLE
[✓] AVB_ROLLBACK

Board Config: 14/14
```
