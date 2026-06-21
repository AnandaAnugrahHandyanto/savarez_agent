# HAL & Interface Audit Reference

## Purpose

Validate hardware abstraction layers.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| HAL package declarations | 20% | PRODUCT_PACKAGES |
| Vendor HAL directories | 20% | hardware/*/ |
| PRODUCT_PACKAGES entries | 20% | Package list |
| android.hardware.* interfaces | 20% | HIDL/AIDL |
| HAL manifest | 20% | manifest.xml |

## Detection Methods

### HAL Package Declarations

```bash
grep -q "PRODUCT_PACKAGES" device/*/BoardConfig.mk device/*/device.mk 2>/dev/null | head -1 | grep -q . && echo "[✓] HAL packages"
```

### Vendor HAL Directories

```bash
find hardware/ -maxdepth 2 -type d 2>/dev/null | head -1 | grep -q . && echo "[✓] Vendor HAL dirs"
```

### PRODUCT_PACKAGES Entries

```bash
grep -r "PRODUCT_PACKAGES" device/ 2>/dev/null | head -1 | grep -q . && echo "[✓] PRODUCT_PACKAGES"
```

### android.hardware.* Interfaces

```bash
grep -r "android.hardware" device/ 2>/dev/null | head -1 | grep -q . && echo "[✓] HIDL/AIDL interfaces"
```

### HAL Manifest

```bash
find device/ -name "manifest.xml" -o -name "compatibility_matrix.xml" 2>/dev/null | head -1 | grep -q . && echo "[✓] HAL manifest"
```

## Score

15 points max (5 checks × 3 points)

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Generic grep matches | Check specific patterns |
| Missing HIDL | Check AIDL fallback |
| Manifest variants | Check either manifest |
| Package naming | Check PRODUCT_PACKAGES |
