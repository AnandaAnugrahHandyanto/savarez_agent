# Kernel Ecosystem Audit Reference

## Overview

Validates kernel integration, model, DTBO, and root frameworks.

---

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| TARGET_KERNEL_SOURCE | 18.75% | Kernel source path |
| TARGET_KERNEL_CONFIG | 18.75% | Kernel config |
| BOARD_KERNEL_CMDLINE | 12.5% | Kernel cmdline |
| Kernel Model | 6.25% | Model detected |
| DTBO Prebuilt | 6.25% | DTBO image |
| DTBO Config | 6.25% | DTBO config |
| KernelSU | 12.5% | Root framework |
| SUSFS | 6.25% | SUSFS support |

---

## Scoring

| Check | Pass | Fail |
|-------|------|------|
| TARGET_KERNEL_SOURCE | +3 | 0 |
| TARGET_KERNEL_CONFIG | +3 | 0 |
| BOARD_KERNEL_CMDLINE | +2 | 0 |
| Kernel Model | +1 | 0 |
| DTBO Prebuilt | +1 | 0 |
| DTBO Config | +1 | 0 |
| KernelSU detected | +1 | 0 |
| SUSFS | +1 | 0 |
| Additional | +4 | 0 |
| **Total** | **16** | |

---

## Kernel Model Detection

### Legacy

- TARGET_KERNEL_SOURCE present
- No GKI indicators

### GKI

- GKI_KERNEL_VERSION present, OR
- TARGET_PREBUILT_KERNEL present
- No local kernel source

### Hybrid

- Both kernel source AND prebuilt

---

## DTBO Detection

### Prebuilt

```bash
BOARD_PREBUILT_DTBOIMAGE=dtbo.img
```

### Kernel-built

```bash
TARGET_DTBO_CFG=onyx_dtbo.cfg
```

### False-Positive Prevention

Check for BOTH indicators, not just one.

---

## KernelSU Detection

### Requirements

1. At least 2 `KERNELSU` references (uppercase)
2. At least 1 hook indicator (`ksu_hook`, `allow_su`, `ksu_handle`)

### False-Positive Prevention

- Do NOT match generic `ksu` string
- Require uppercase `KERNELSU`
- Require hook indicator

### Frameworks

| Framework | Detection |
|-----------|-----------|
| KernelSU | KERNELSU + hooks |
| KernelSU Next | KERNELSU + KSU_NEXT |
| None | No indicators |

---

## SUSFS Detection

```bash
SUSFS=$(grep -c "SUSFS\|susfs" kernel/ 2>/dev/null || echo "0")
```

---

## Example Output

```
=== Kernel Ecosystem Audit ===

[✓] TARGET_KERNEL_SOURCE
[✓] TARGET_KERNEL_CONFIG
[✓] BOARD_KERNEL_CMDLINE
Kernel Model: GKI
[✓] DTBO prebuilt: dtbo.img
[✓] DTBO config: onyx_dtbo.cfg
DTBO Status: READY
Root Framework: KernelSU
SUSFS: Present

Kernel Ecosystem: 16/16
```
