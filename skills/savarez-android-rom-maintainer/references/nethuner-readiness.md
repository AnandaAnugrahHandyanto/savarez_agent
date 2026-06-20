# NetHunter Readiness Reference

## Overview

Audits NetHunter-specific kernel requirements.
Informational only — does not affect ROM Readiness score.

---

## Required Configs (Scored)

| Config | Weight | Description |
|--------|--------|-------------|
| CONFIG_USB_CONFIGFS | 16.67% | USB gadget core |
| CONFIG_USB_CONFIGFS_F_HID | 16.67% | HID gadget |
| CONFIG_USB_CONFIGFS_RNDIS | 16.67% | RNDIS network |
| CONFIG_CFG80211 | 16.67% | WiFi core |
| CONFIG_MAC80211 | 16.67% | WiFi mac |
| CONFIG_PACKET | 16.67% | Raw packet |

---

## Informational Configs (Not Scored)

| Config | Description |
|--------|-------------|
| CONFIG_USB_CONFIGFS_ECM | ECM network |
| CONFIG_USB_CONFIGFS_NCM | NCM network |
| CONFIG_BT_HCIBTUSB | Bluetooth USB |

---

## Scoring

| Checks | Points |
|--------|--------|
| 6 required configs | 100 |

### Category

| Score | Category |
|-------|----------|
| 80-100 | READY |
| 50-79 | PARTIAL |
| 0-49 | NOT READY |

---

## Kernel Version Considerations

| Config | Kernel 4.x | Kernel 5.x | Kernel 6.x |
|--------|------------|------------|------------|
| CONFIG_USB_CONFIGFS | ✅ | ✅ | ✅ |
| CONFIG_USB_CONFIGFS_F_HID | ✅ | ✅ | ✅ |
| CONFIG_USB_CONFIGFS_RNDIS | ✅ | ✅ | ✅ |
| CONFIG_CFG80211 | ✅ | ✅ | ✅ |
| CONFIG_MAC80211 | ✅ | ✅ | ✅ |
| CONFIG_PACKET | ✅ | ✅ | ✅ |
| CONFIG_BT_HCIBTUSB | ✅ | ✅ | ✅ |

---

## Example Output

```
=== NetHunter Readiness ===

[✓] CONFIG_USB_CONFIGFS
[✓] CONFIG_USB_CONFIGFS_F_HID
[✓] CONFIG_USB_CONFIGFS_RNDIS
[✓] CONFIG_CFG80211
[✓] CONFIG_MAC80211
[✓] CONFIG_PACKET

Informational:
[✓] CONFIG_USB_CONFIGFS_ECM
[ ] CONFIG_USB_CONFIGFS_NCM
[✓] CONFIG_BT_HCIBTUSB

NetHunter Readiness: 100/100
Category: READY
```
