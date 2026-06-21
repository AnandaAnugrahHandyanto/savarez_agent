# Hardware Ecosystem Audit Reference

## Purpose

Validate hardware initialization readiness.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Init scripts | 20% | init.rc, init.*.rc |
| Fstab configuration | 20% | fstab.*.vendor |
| Overlay configuration | 20% | device overlays |
| Architecture validation | 20% | ARM/ARM64 |
| Device manifest | 20% | manifest.xml |

## Detection Methods

### Init Scripts

```bash
find device/ -name "init*.rc" 2>/dev/null | head -1 | grep -q . && echo "[✓] Init scripts"
```

### Fstab Configuration

```bash
find device/ -name "fstab.*" 2>/dev/null | head -1 | grep -q . && echo "[✓] Fstab config"
```

### Overlay Configuration

```bash
find device/ -name "overlay" -type d 2>/dev/null | head -1 | grep -q . && echo "[✓] Overlay config"
```

### Architecture Validation

```bash
grep -q "TARGET_ARCH" BoardConfig.mk 2>/dev/null && echo "[✓] Architecture"
```

### Device Manifest

```bash
find device/ -name "manifest.xml" 2>/dev/null | head -1 | grep -q . && echo "[✓] Device manifest"
```

## Score

15 points max (5 checks × 3 points)

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Multiple init scripts | Check presence only |
| Vendor tree naming | Check vendor/ or device/ |
| Overlay variants | Check overlay/ directory |
| Manifest variants | Check manifest.xml or compatibility_matrix.xml |
