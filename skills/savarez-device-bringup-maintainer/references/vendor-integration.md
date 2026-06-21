# Vendor Integration Audit Reference

## Purpose

Validate vendor tree integration for bring-up.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Vendor Tree | 20% | vendor/ directory |
| Blob List | 20% | proprietary-files.txt |
| Extraction Scripts | 20% | extract-files.sh |
| Blob Presence | 20% | Blobs available |
| Vendor Overlays | 20% | Overlay configs |

## Detection Methods

### Vendor Tree

```bash
[ -d "vendor/" ] && echo "[✓] Vendor Tree"
```

### Blob List

```bash
find vendor/ -name "proprietary-files.txt" 2>/dev/null | head -1 | grep -q . && echo "[✓] Blob List"
```

### Extraction Scripts

```bash
find vendor/ -name "extract-files.sh" 2>/dev/null | head -1 | grep -q . && echo "[✓] Extraction Scripts"
```

### Blob Presence

```bash
find vendor/ -name "*.so" -o -name "*.bin" -o -name "*.fw" 2>/dev/null | head -1 | grep -q . && echo "[✓] Blob Presence"
```

### Vendor Overlays

```bash
find vendor/ -name "overlay" -type d 2>/dev/null | head -1 | grep -q . && echo "[✓] Vendor Overlays"
```

## Score

15 points max (5 checks × 3 points)

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Blobs in device tree | Check vendor/ first |
| Missing extract script | Report as warning |
| Overlay naming | Check overlay/ directory |
| Blob file types | Check .so, .bin, .fw |
