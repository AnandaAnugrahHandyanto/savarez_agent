# Partition Layout Audit Reference

## Purpose

Validate partition layout for first boot.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| System partition | 25% | System image |
| Vendor partition | 25% | Vendor image |
| Product partition | 25% | Product image |
| Super partition | 25% | Dynamic partitions |

## Detection Methods

### System Partition

```bash
grep -q "BOARD_SYSTEMIMAGE_PARTITION_SIZE" BoardConfig.mk 2>/dev/null && echo "[✓] System partition"
```

### Vendor Partition

```bash
grep -q "BOARD_VENDORIMAGE_PARTITION_SIZE" BoardConfig.mk 2>/dev/null && echo "[✓] Vendor partition"
```

### Product Partition

```bash
grep -q "BOARD_PRODUCTIMAGE_PARTITION_SIZE" BoardConfig.mk 2>/dev/null && echo "[✓] Product partition"
```

### Super Partition

```bash
grep -q "TARGET_USE_DYNAMIC_PARTITIONS\|BOARD_SUPER_PARTITION" BoardConfig.mk 2>/dev/null && echo "[✓] Super partition"
```

## Score

16 points max (4 checks × 4 points)

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Dynamic partitions vary | Check super partition |
| Missing partition size | Check partition name |
| A/B partitions | Check either A or B |
