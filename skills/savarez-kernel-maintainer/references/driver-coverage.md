# Driver Coverage Audit Reference

## Purpose

Evaluate kernel subsystem coverage.

## Two-Phase Evaluation

### Phase 1: Source Coverage

| Subsystem | Path |
|-----------|------|
| USB | drivers/usb/ |
| WiFi | drivers/net/wireless/ |
| Bluetooth | drivers/bluetooth/ |
| HID | drivers/hid/ |
| Media | drivers/media/ |
| Sensors | drivers/iio/ |

### Phase 2: Config Coverage

| Subsystem | Configs |
|-----------|---------|
| USB | CONFIG_USB, CONFIG_USB_GADGET |
| WiFi | CONFIG_CFG80211, CONFIG_MAC80211 |
| Bluetooth | CONFIG_BT, CONFIG_BT_HCIBTUSB |
| HID | CONFIG_HID, CONFIG_USB_HID |
| Media | CONFIG_MEDIA_SUPPORT, CONFIG_VIDEO_DEV |
| Sensors | CONFIG_IIO, CONFIG_SENSORS |

## Scoring

| Score | Category |
|-------|----------|
| 18-20 | READY |
| 12-17 | PARTIAL |
| 0-11 | NOT READY |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Module vs built-in | Check =y only |
| Subsystem overlap | Count per subsystem |

## Note

Informational only — does not affect readiness score.

## Example Output

```
=== Driver Coverage Audit ===

Source Coverage:
[✓] USB
[✓] WiFi
[✓] Bluetooth
[✓] HID
[✓] Media
[✓] Sensors
Source: 6/6

Config Coverage:
[✓] CONFIG_USB
[✓] CONFIG_USB_GADGET
[✓] CONFIG_CFG80211
[✓] CONFIG_MAC80211
[✓] CONFIG_BT
[✓] CONFIG_BT_HCIBTUSB
[✓] CONFIG_HID
[✓] CONFIG_USB_HID
[✓] CONFIG_MEDIA_SUPPORT
[✓] CONFIG_VIDEO_DEV
[✓] CONFIG_IIO
[ ] CONFIG_SENSORS
Config: 11/12

Driver Coverage: Source 6/6, Config 11/12
Category: READY
```
