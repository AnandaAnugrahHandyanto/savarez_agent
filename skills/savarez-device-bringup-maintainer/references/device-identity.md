# Device Identity Audit Reference

## Purpose

Validate device identification for bring-up.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Device codename | 25% | Primary codename |
| Board name | 25% | Board identifier |
| SoC family | 25% | Qualcomm/MediaTek |
| Android target | 25% | Android version |

## Detection Methods

### Device Codename

```bash
[ -d "device/*/" ] && echo "[✓] Device codename"
```

### Board Name

```bash
grep -q "TARGET_BOARD" BoardConfig.mk 2>/dev/null && echo "[✓] Board name"
```

### SoC Family

```bash
grep -r "TARGET_BOARD_PLATFORM" device/ 2>/dev/null | grep -qE "qcom|mtk|exynos|tensor" && echo "[✓] SoC family"
```

### Android Target

```bash
grep -q "PLATFORM_VERSION" BoardConfig.mk 2>/dev/null && echo "[✓] Android target"
```

## Score

16 points max (4 checks × 4 points)

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Multiple device trees | Check primary device tree only |
| SoC naming variants | Normalize platform names |
