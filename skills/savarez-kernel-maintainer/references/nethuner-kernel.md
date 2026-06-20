# NetHunter Kernel Reference

## Purpose

Audit NetHunter kernel requirements.

## Required Configs (Scored)

| Config | Description |
|--------|-------------|
| CONFIG_USB_CONFIGFS | USB gadget core |
| CONFIG_USB_CONFIGFS_F_HID | HID gadget |
| CONFIG_USB_CONFIGFS_RNDIS | RNDIS network |
| CONFIG_CFG80211 | WiFi core |
| CONFIG_MAC80211 | WiFi mac |
| CONFIG_PACKET | Raw packet |

## Scoring

| Score | Category |
|-------|----------|
| 80-100 | READY |
| 50-79 | PARTIAL |
| 0-49 | NOT READY |

## Note

Informational only — does not affect readiness score.

## Example Output

```
=== NetHunter Readiness ===

[✓] CONFIG_USB_CONFIGFS
[✓] CONFIG_USB_CONFIGFS_F_HID
[✓] CONFIG_USB_CONFIGFS_RNDIS
[✓] CONFIG_CFG80211
[✓] CONFIG_MAC80211
[✓] CONFIG_PACKET

NetHunter Readiness: 100/100
Category: READY
```
