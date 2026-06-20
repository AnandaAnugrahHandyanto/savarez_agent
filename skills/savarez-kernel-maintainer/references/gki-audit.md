# GKI Audit Reference

## Purpose

Detect GKI (Generic Kernel Image) configuration.

## Kernel Model Detection

| Model | Indicators |
|-------|------------|
| Legacy | No GKI indicators |
| GKI | GKI_KERNEL_VERSION or prebuilt |
| Hybrid | Both source and prebuilt |

## Checks

| Check | Description |
|-------|-------------|
| GKI_KERNEL_VERSION | GKI version defined |
| Prebuilt kernel | Prebuilt references |
| vendor_boot | Vendor boot configured |

## Detection Logic

```bash
if [ -n "$GKI_VERSION" ] || [ -n "$PREBUILT" ]; then
    if [ -n "$KERNEL_SRC" ]; then
        KMODEL="Hybrid"
    else
        KMODEL="GKI"
    fi
else
    KMODEL="Legacy"
fi
```

## Note

Informational only — does not affect readiness score.

## Example Output

```
=== GKI Audit ===

Kernel Model: GKI
[✓] GKI_KERNEL_VERSION: 5.15.148
[✓] Prebuilt kernel: PRESENT
[✓] vendor_boot: CONFIGURED
```
