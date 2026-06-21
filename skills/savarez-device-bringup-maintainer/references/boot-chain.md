# Boot Chain Audit Reference

## Purpose

Validate boot chain for first boot.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Bootloader config | 25% | Bootloader present |
| Kernel image | 25% | Kernel prebuilt/source |
| Ramdisk config | 25% | Ramdisk defined |
| DTB/DTBO | 25% | Device tree |

## Detection Methods

### Bootloader Config

```bash
grep -q "TARGET_BOOTLOADER\|BOARD_BOOTLOADER" BoardConfig.mk 2>/dev/null && echo "[✓] Bootloader"
```

### Kernel Image

```bash
grep -q "TARGET_KERNEL_IMAGE\|TARGET_PREBUILT_KERNEL" BoardConfig.mk 2>/dev/null && echo "[✓] Kernel image"
```

### Ramdisk Config

```bash
grep -q "BOARD_RAMDISK_SIZE" BoardConfig.mk 2>/dev/null && echo "[✓] Ramdisk"
```

### DTB/DTBO

```bash
grep -q "BOARD_PREBUILT_DTBOIMAGE\|TARGET_DTBO" BoardConfig.mk 2>/dev/null && echo "[✓] DTB/DTBO"
```

## Score

16 points max (4 checks × 4 points)

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Prebuilt vs source kernel | Check presence only |
| DTBO variants | Check either prebuilt or source |
| Bootloader naming | Check multiple patterns |
