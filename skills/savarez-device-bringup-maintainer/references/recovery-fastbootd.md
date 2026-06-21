# Recovery & Fastbootd Audit Reference

## Purpose

Validate recovery and fastbootd modes.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Recovery config | 25% | Recovery defined |
| Recovery resources | 25% | Recovery resources |
| Fastboot support | 25% | Fastboot enabled |
| Fastbootd support | 25% | Fastbootd enabled |

## Detection Methods

### Recovery Config

```bash
grep -q "TARGET_RECOVERY\|BOARD_RECOVERY" BoardConfig.mk 2>/dev/null && echo "[✓] Recovery config"
```

### Recovery Resources

```bash
[ -d "device/*/recovery" ] && echo "[✓] Recovery resources"
```

### Fastboot Support

```bash
grep -q "BOARD_FASTBOOT" BoardConfig.mk 2>/dev/null && echo "[✓] Fastboot support"
```

### Fastbootd Support

```bash
grep -q "TARGET_USES_FASTBOOTD" BoardConfig.mk 2>/dev/null && echo "[✓] Fastbootd support"
```

## Score

16 points max (4 checks × 4 points)

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Recovery naming variants | Check multiple patterns |
| Minimal recovery | Check config only |
| Fastboot vs fastbootd | Check both separately |
