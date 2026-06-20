# External WiFi Audit Reference

## Purpose

Audit external WiFi adapter support.

## Two-Phase Evaluation

### Phase 1: Source Availability

| Source | Path |
|--------|------|
| Realtek | drivers/net/wireless/realtek/ |
| Atheros | drivers/net/wireless/atheros/ |
| MediaTek | drivers/net/wireless/mediatek/ |

### Phase 2: Config Enablement

| Adapter | Config | Priority |
|---------|--------|----------|
| rtl8188eu | CONFIG_RTL8188EU | HIGH |
| rtl8812au | CONFIG_RTL8812AU | HIGH |
| rtl88x2bu | CONFIG_RTL88X2BU | HIGH |
| ath9k_htc | CONFIG_ATH9K_HTC | HIGH |
| rtl8xxxu | CONFIG_RTL8XXXU | MEDIUM |
| rtw88 | CONFIG_RTW88 | MEDIUM |
| rtw89 | CONFIG_RTW89 | MEDIUM |
| mt76 | CONFIG_MT76 | MEDIUM |

## Scoring

| Category | Score |
|----------|-------|
| READY | 16-20 |
| PARTIAL | 10-15 |
| NOT READY | 0-9 |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Config as module | Check =y only |
| Missing adapter | Report as not supported |

## Note

Informational only — does not affect readiness score.

## Example Output

```
=== External WiFi Audit ===

Source Availability:
[✓] Realtek
[✓] Atheros
[✓] MediaTek
Source: 3/3

Config Enablement:
[✓] rtl8188eu
[✓] rtl8812au
[ ] rtl88x2bu
[✓] ath9k_htc
[ ] rtl8xxxu
[✓] rtw88
[ ] rtw89
[✓] mt76
Config: 13/20

Category: PARTIAL
```
