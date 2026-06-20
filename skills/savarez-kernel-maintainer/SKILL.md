---
name: savarez-kernel-maintainer
description: "Android kernel maintenance: health audit, defconfig, GKI, modules, KernelSU/SUSFS, NetHunter, external WiFi, driver coverage, security, and release readiness."
version: 1.0.0
author: Savarez Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [android, kernel, gki, kernelsu, susfs, nethunter, wifi, security]
    related_skills: [savarez-android-rom-maintainer, savarez-git-maintainer]
---

# Savarez Kernel Maintainer

## Overview

Standalone skill for Android kernel maintenance.
Covers: GKI auditing, KernelSU ecosystems, NetHunter readiness, external WiFi support, driver coverage, and kernel release readiness.

Complements:
- savarez-git-maintainer (fork health)
- savarez-release-manager (release workflow)
- savarez-android-rom-maintainer (ROM-level maintenance)

## When to Use

- Before kernel build
- During kernel bring-up
- When auditing kernel config
- When checking KernelSU compatibility
- When preparing kernel release
- When validating NetHunter support

---

## Capabilities Overview (16)

| # | Capability | Category |
|---|------------|----------|
| 1 | Kernel Health Audit | CRITICAL |
| 2 | Defconfig Audit | CRITICAL |
| 3 | GKI Audit | INFORMATIONAL |
| 4 | Module Audit | CRITICAL |
| 5 | Root Ecosystem Audit | MEDIUM |
| 6 | NetHunter Readiness | INFORMATIONAL |
| 7 | External WiFi Audit | INFORMATIONAL |
| 8 | HID Gadget Audit | INFORMATIONAL |
| 9 | ConfigFS Audit | INFORMATIONAL |
| 10 | USB Arsenal Audit | INFORMATIONAL |
| 11 | Driver Coverage Audit | INFORMATIONAL |
| 12 | Security Audit | MEDIUM |
| 13 | Patch Conflict Detection | MEDIUM |
| 14 | Upstream Sync Readiness | MEDIUM |
| 15 | Build Configuration Audit | LOWER |
| 16 | Release Readiness | LOWER |

---

## Hard-Fail Logic

### Critical Components

| Component | Weight | Max Points |
|-----------|--------|------------|
| Kernel Health | 15% | 15 |
| Defconfig | 15% | 16 |
| Module | 12% | 12 |
| **Total Critical** | **42%** | **43** |

### Rules

| Failures | Max Score | Category |
|----------|-----------|----------|
| 0 | 100 | Normal |
| 1 | 49 | BRING-UP |
| 2 | 25 | NOT READY |
| 3 | 10 | NOT READY |

---

## Capability 1: Kernel Health Audit

**Category:** CRITICAL

**Purpose:** Overall kernel source health check.

**Checks:**

| Check | Weight | Description |
|-------|--------|-------------|
| Makefile | 20% | Root Makefile exists |
| Kconfig | 20% | Root Kconfig exists |
| arch/ | 20% | Architecture directory |
| drivers/ | 20% | Drivers directory |
| scripts/ | 20% | Build scripts |

**How to Run:**

```bash
echo "=== Kernel Health Audit ==="
KRN_HEALTH=0

[ -f "Makefile" ] && echo "[✓] Makefile" && KRN_HEALTH=$((KRN_HEALTH + 3)) || echo "[ ] Makefile"
[ -f "Kconfig" ] && echo "[✓] Kconfig" && KRN_HEALTH=$((KRN_HEALTH + 3)) || echo "[ ] Kconfig"
[ -d "arch" ] && echo "[✓] arch/" && KRN_HEALTH=$((KRN_HEALTH + 3)) || echo "[ ] arch/"
[ -d "drivers" ] && echo "[✓] drivers/" && KRN_HEALTH=$((KRN_HEALTH + 3)) || echo "[ ] drivers/"
[ -d "scripts" ] && echo "[✓] scripts/" && KRN_HEALTH=$((KRN_HEALTH + 3)) || echo "[ ] scripts/"

echo "Kernel Health: $KRN_HEALTH/15"
```

**Score:** 15 points max

---

## Capability 2: Defconfig Audit

**Category:** CRITICAL

**Purpose:** Validate kernel defconfig.

**Checks:**

| Check | Weight | Description |
|-------|--------|-------------|
| defconfig exists | 25% | Device defconfig present |
| CONFIG_LOCALVERSION | 25% | Local version set |
| CONFIG_MODULES | 25% | Module support enabled |
| CONFIG_SMP | 25% | Symmetric multiprocessing |

**How to Run:**

```bash
echo "=== Defconfig Audit ==="
DEFCONFIG=0

DEFCONFIG_FILE=$(ls arch/*/configs/*_defconfig 2>/dev/null | head -1)
if [ -n "$DEFCONFIG_FILE" ]; then
    echo "[✓] defconfig: $(basename $DEFCONFIG_FILE)"
    DEFCONFIG=$((DEFCONFIG + 4))
else
    echo "[ ] defconfig: MISSING"
fi

grep -q "CONFIG_LOCALVERSION=" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_LOCALVERSION" && DEFCONFIG=$((DEFCONFIG + 4)) || echo "[ ] CONFIG_LOCALVERSION"
grep -q "CONFIG_MODULES=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_MODULES=y" && DEFCONFIG=$((DEFCONFIG + 4)) || echo "[ ] CONFIG_MODULES=y"
grep -q "CONFIG_SMP=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_SMP=y" && DEFCONFIG=$((DEFCONFIG + 4)) || echo "[ ] CONFIG_SMP=y"

echo "Defconfig: $DEFCONFIG/16"
```

**Score:** 16 points max

---

## Capability 3: GKI Audit

**Category:** INFORMATIONAL

**Purpose:** Detect GKI (Generic Kernel Image) configuration.

**Kernel Model Detection:**

| Model | Indicators |
|-------|------------|
| Legacy | No GKI indicators |
| GKI | GKI_KERNEL_VERSION or prebuilt |
| Hybrid | Both source and prebuilt |

**How to Run:**

```bash
echo "=== GKI Audit ==="

KERNEL_SRC=$(grep "TARGET_KERNEL_SOURCE" BoardConfig.mk 2>/dev/null | cut -d= -f2 | tr -d ' ')
GKI_VERSION=$(grep "GKI_KERNEL_VERSION" BoardConfig.mk 2>/dev/null | cut -d= -f2 | tr -d ' ')
PREBUILT=$(grep "TARGET_PREBUILT_KERNEL" BoardConfig.mk 2>/dev/null | cut -d= -f2 | tr -d ' ')

if [ -n "$GKI_VERSION" ] || [ -n "$PREBUILT" ]; then
    if [ -n "$KERNEL_SRC" ]; then
        KMODEL="Hybrid"
    else
        KMODEL="GKI"
    fi
else
    KMODEL="Legacy"
fi

echo "Kernel Model: $KMODEL"

[ -n "$GKI_VERSION" ] && echo "[✓] GKI_KERNEL_VERSION: $GKI_VERSION" || echo "[ ] GKI_KERNEL_VERSION: NOT SET"
[ -n "$PREBUILT" ] && echo "[✓] Prebuilt kernel: PRESENT" || echo "[ ] Prebuilt kernel: NOT SET"
grep -q "BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE" BoardConfig.mk 2>/dev/null && echo "[✓] vendor_boot: CONFIGURED" || echo "[ ] vendor_boot: NOT CONFIGURED"
```

**Note:** Informational only — does not affect readiness score.

---

## Capability 4: Module Audit

**Category:** CRITICAL

**Purpose:** Validate kernel module configuration.

**Checks:**

| Check | Weight | Description |
|-------|--------|-------------|
| drivers/ directory | 25% | Drivers present |
| CONFIG_MODULE | 25% | Module support enabled |
| Key modules | 25% | Essential modules defined |
| Module signing | 25% | Module signing configured |

**How to Run:**

```bash
echo "=== Module Audit ==="
MODULE=0

[ -d "drivers" ] && echo "[✓] drivers/ directory" && MODULE=$((MODULE + 3)) || echo "[ ] drivers/ directory"

DEFCONFIG_FILE=$(ls arch/*/configs/*_defconfig 2>/dev/null | head -1)
grep -q "CONFIG_MODULE=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_MODULE=y" && MODULE=$((MODULE + 3)) || echo "[ ] CONFIG_MODULE=y"
grep -q "CONFIG_MODULES=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_MODULES=y" && MODULE=$((MODULE + 3)) || echo "[ ] CONFIG_MODULES=y"
grep -q "CONFIG_MODULE_SIG" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] Module signing" && MODULE=$((MODULE + 3)) || echo "[ ] Module signing"

echo "Module: $MODULE/12"
```

**Score:** 12 points max

---

## Capability 5: Root Ecosystem Audit

**Category:** MEDIUM

**Purpose:** Detect KernelSU, KernelSU Next, SUSFS, and root frameworks.

**Detection Matrix:**

| Framework | Detection |
|-----------|-----------|
| KernelSU Next + SUSFS | KERNELSU ≥2 + hooks ≥1 + KSU_NEXT + SUSFS ≥2 |
| KernelSU + SUSFS | KERNELSU ≥2 + hooks ≥1 + SUSFS ≥2 |
| KernelSU Next | KERNELSU ≥2 + hooks ≥1 + KSU_NEXT |
| KernelSU | KERNELSU ≥2 + hooks ≥1 |
| KernelSU (partial) | KERNELSU ≥1 only |
| None | No indicators |

**How to Run:**

```bash
echo "=== Kernel Root Ecosystem Audit ==="

KSU_UPPER=$(grep -c "KERNELSU" kernel/ 2>/dev/null || echo "0")
KSU_HOOKS=$(grep -c "ksu_hook\|allow_su\|ksu_handle" kernel/ 2>/dev/null || echo "0")
KSU_NEXT=$(grep -c "KSU_NEXT\|ksu_next" kernel/ 2>/dev/null || echo "0")
SUSFS_REFS=$(grep -c "SUSFS\|susfs" kernel/ 2>/dev/null || echo "0")

if [ "$KSU_UPPER" -gt 2 ] && [ "$KSU_HOOKS" -gt 0 ]; then
    if [ "$KSU_NEXT" -gt 0 ]; then
        if [ "$SUSFS_REFS" -gt 1 ]; then
            FRAMEWORK="KernelSU Next + SUSFS"
            ROOT_SCORE=10
        else
            FRAMEWORK="KernelSU Next"
            ROOT_SCORE=8
        fi
    elif [ "$SUSFS_REFS" -gt 1 ]; then
        FRAMEWORK="KernelSU + SUSFS"
        ROOT_SCORE=9
    else
        FRAMEWORK="KernelSU"
        ROOT_SCORE=7
    fi
elif [ "$KSU_UPPER" -gt 0 ]; then
    FRAMEWORK="KernelSU (partial)"
    ROOT_SCORE=4
else
    FRAMEWORK="None"
    ROOT_SCORE=0
fi

echo "Framework: $FRAMEWORK"
echo "KernelSU: $KSU_UPPER refs, $KSU_HOOKS hooks"
echo "SUSFS: $SUSFS_REFS refs"
echo "Root Ecosystem: $ROOT_SCORE/10"
```

**Score:** 10 points max

---

## Capability 6: NetHunter Readiness

**Category:** INFORMATIONAL

**Purpose:** Audit NetHunter kernel requirements.

**Required Configs (scored):**

| Config | Description |
|--------|-------------|
| CONFIG_USB_CONFIGFS | USB gadget core |
| CONFIG_USB_CONFIGFS_F_HID | HID gadget |
| CONFIG_USB_CONFIGFS_RNDIS | RNDIS network |
| CONFIG_CFG80211 | WiFi core |
| CONFIG_MAC80211 | WiFi mac |
| CONFIG_PACKET | Raw packet |

**How to Run:**

```bash
echo "=== NetHunter Readiness ==="
NH_SCORE=0
DEFCONFIG_FILE=$(ls arch/*/configs/*_defconfig 2>/dev/null | head -1)

grep -q "CONFIG_USB_CONFIGFS=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_USB_CONFIGFS"
grep -q "CONFIG_USB_CONFIGFS_F_HID=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS_F_HID" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_USB_CONFIGFS_F_HID"
grep -q "CONFIG_USB_CONFIGFS_RNDIS=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS_RNDIS" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_USB_CONFIGFS_RNDIS"
grep -q "CONFIG_CFG80211=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_CFG80211" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_CFG80211"
grep -q "CONFIG_MAC80211=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_MAC80211" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_MAC80211"
grep -q "CONFIG_PACKET=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_PACKET" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_PACKET"

PERCENT=$((NH_SCORE * 100 / 6))
echo ""
echo "NetHunter Readiness: $PERCENT/100"

if [ "$PERCENT" -ge 80 ]; then
    echo "Category: READY"
elif [ "$PERCENT" -ge 50 ]; then
    echo "Category: PARTIAL"
else
    echo "Category: NOT READY"
fi
```

**Note:** Informational only — does not affect readiness score.

---

## Capability 7: External WiFi Audit

**Category:** INFORMATIONAL

**Purpose:** Audit external WiFi adapter support.

**Two-Phase Evaluation:**

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

**How to Run:**

```bash
echo "=== External WiFi Audit ==="
DEFCONFIG_FILE=$(ls arch/*/configs/*_defconfig 2>/dev/null | head -1)

# Phase 1: Source Availability
echo "Source Availability:"
WIFI_SRC=0
[ -d "drivers/net/wireless/realtek" ] && echo "[✓] Realtek" && WIFI_SRC=$((WIFI_SRC + 1)) || echo "[ ] Realtek"
[ -d "drivers/net/wireless/atheros" ] && echo "[✓] Atheros" && WIFI_SRC=$((WIFI_SRC + 1)) || echo "[ ] Atheros"
[ -d "drivers/net/wireless/mediatek" ] && echo "[✓] MediaTek" && WIFI_SRC=$((WIFI_SRC + 1)) || echo "[ ] MediaTek"
echo "Source: $WIFI_SRC/3"

# Phase 2: Config Enablement
echo ""
echo "Config Enablement:"
WIFI_CFG=0
grep -q "CONFIG_RTL8188EU=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] rtl8188eu" && WIFI_CFG=$((WIFI_CFG + 4)) || echo "[ ] rtl8188eu"
grep -q "CONFIG_RTL8812AU=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] rtl8812au" && WIFI_CFG=$((WIFI_CFG + 4)) || echo "[ ] rtl8812au"
grep -q "CONFIG_RTL88X2BU=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] rtl88x2bu" && WIFI_CFG=$((WIFI_CFG + 4)) || echo "[ ] rtl88x2bu"
grep -q "CONFIG_ATH9K_HTC=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] ath9k_htc" && WIFI_CFG=$((WIFI_CFG + 4)) || echo "[ ] ath9k_htc"
grep -q "CONFIG_RTL8XXXU=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] rtl8xxxu" && WIFI_CFG=$((WIFI_CFG + 1)) || echo "[ ] rtl8xxxu"
grep -q "CONFIG_RTW88=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] rtw88" && WIFI_CFG=$((WIFI_CFG + 1)) || echo "[ ] rtw88"
grep -q "CONFIG_RTW89=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] rtw89" && WIFI_CFG=$((WIFI_CFG + 1)) || echo "[ ] rtw89"
grep -q "CONFIG_MT76=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] mt76" && WIFI_CFG=$((WIFI_CFG + 1)) || echo "[ ] mt76"
echo "Config: $WIFI_CFG/20"

# Category
if [ "$WIFI_CFG" -ge 16 ]; then
    echo "Category: READY"
elif [ "$WIFI_CFG" -ge 10 ]; then
    echo "Category: PARTIAL"
else
    echo "Category: NOT READY"
fi
```

**Note:** Informational only — does not affect readiness score.

---

## Capability 8: HID Gadget Audit

**Category:** INFORMATIONAL

**Purpose:** Audit HID gadget support.

**Checks:**

| Config | Description |
|--------|-------------|
| CONFIG_USB_HID | USB HID core |
| CONFIG_USB_CONFIGFS_F_HID | ConfigFS HID |
| CONFIG_HID_GENERIC | Generic HID |

**How to Run:**

```bash
echo "=== HID Gadget Audit ==="
HID_SCORE=0
DEFCONFIG_FILE=$(ls arch/*/configs/*_defconfig 2>/dev/null | head -1)

grep -q "CONFIG_USB_HID=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_USB_HID" && HID_SCORE=$((HID_SCORE + 1)) || echo "[ ] CONFIG_USB_HID"
grep -q "CONFIG_USB_CONFIGFS_F_HID=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS_F_HID" && HID_SCORE=$((HID_SCORE + 1)) || echo "[ ] CONFIG_USB_CONFIGFS_F_HID"
grep -q "CONFIG_HID_GENERIC=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_HID_GENERIC" && HID_SCORE=$((HID_SCORE + 1)) || echo "[ ] CONFIG_HID_GENERIC"

echo "HID Gadget: $HID_SCORE/3"
```

**Note:** Informational only — does not affect readiness score.

---

## Capability 9: ConfigFS Audit

**Category:** INFORMATIONAL

**Purpose:** Audit USB ConfigFS support.

**Checks:**

| Config | Description |
|--------|-------------|
| CONFIG_USB_CONFIGFS | ConfigFS core |
| CONFIG_USB_CONFIGFS_F_HID | HID function |
| CONFIG_USB_CONFIGFS_F_RNDIS | RNDIS function |
| CONFIG_USB_CONFIGFS_F_ECM | ECM function |
| CONFIG_USB_CONFIGFS_F_NCM | NCM function |
| CONFIG_USB_F_MASS_STORAGE | Mass storage |

**How to Run:**

```bash
echo "=== ConfigFS Audit ==="
CONFIGFS=0
DEFCONFIG_FILE=$(ls arch/*/configs/*_defconfig 2>/dev/null | head -1)

grep -q "CONFIG_USB_CONFIGFS=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS" && CONFIGFS=$((CONFIGFS + 1)) || echo "[ ] CONFIG_USB_CONFIGFS"
grep -q "CONFIG_USB_CONFIGFS_F_HID=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS_F_HID" && CONFIGFS=$((CONFIGFS + 1)) || echo "[ ] CONFIG_USB_CONFIGFS_F_HID"
grep -q "CONFIG_USB_CONFIGFS_F_RNDIS=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS_F_RNDIS" && CONFIGFS=$((CONFIGFS + 1)) || echo "[ ] CONFIG_USB_CONFIGFS_F_RNDIS"
grep -q "CONFIG_USB_CONFIGFS_F_ECM=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS_F_ECM" && CONFIGFS=$((CONFIGFS + 1)) || echo "[ ] CONFIG_USB_CONFIGFS_F_ECM"
grep -q "CONFIG_USB_CONFIGFS_F_NCM=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS_F_NCM" && CONFIGFS=$((CONFIGFS + 1)) || echo "[ ] CONFIG_USB_CONFIGFS_F_NCM"
grep -q "CONFIG_USB_F_MASS_STORAGE=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_USB_F_MASS_STORAGE" && CONFIGFS=$((CONFIGFS + 1)) || echo "[ ] CONFIG_USB_F_MASS_STORAGE"

echo "ConfigFS: $CONFIGFS/6"
```

**Note:** Informational only — does not affect readiness score.

---

## Capability 10: USB Arsenal Audit

**Category:** INFORMATIONAL

**Purpose:** Comprehensive USB gadget audit.

**Checks:**

| Config | Category |
|--------|----------|
| CONFIG_USB_CONFIGFS | Core |
| CONFIG_USB_CONFIGFS_F_HID | HID |
| CONFIG_USB_CONFIGFS_F_RNDIS | Network |
| CONFIG_USB_CONFIGFS_F_ECM | Network |
| CONFIG_USB_CONFIGFS_F_NCM | Network |
| CONFIG_USB_F_MASS_STORAGE | Storage |
| CONFIG_USB_STORAGE | Storage |
| CONFIG_USB_U_ETHER | Ethernet |

**How to Run:**

```bash
echo "=== USB Arsenal Audit ==="
USB_SCORE=0
DEFCONFIG_FILE=$(ls arch/*/configs/*_defconfig 2>/dev/null | head -1)

grep -q "CONFIG_USB_CONFIGFS=y" "$DEFCONFIG_FILE" 2>/dev/null && USB_SCORE=$((USB_SCORE + 1))
grep -q "CONFIG_USB_CONFIGFS_F_HID=y" "$DEFCONFIG_FILE" 2>/dev/null && USB_SCORE=$((USB_SCORE + 1))
grep -q "CONFIG_USB_CONFIGFS_F_RNDIS=y" "$DEFCONFIG_FILE" 2>/dev/null && USB_SCORE=$((USB_SCORE + 1))
grep -q "CONFIG_USB_CONFIGFS_F_ECM=y" "$DEFCONFIG_FILE" 2>/dev/null && USB_SCORE=$((USB_SCORE + 1))
grep -q "CONFIG_USB_CONFIGFS_F_NCM=y" "$DEFCONFIG_FILE" 2>/dev/null && USB_SCORE=$((USB_SCORE + 1))
grep -q "CONFIG_USB_F_MASS_STORAGE=y" "$DEFCONFIG_FILE" 2>/dev/null && USB_SCORE=$((USB_SCORE + 1))
grep -q "CONFIG_USB_STORAGE=y" "$DEFCONFIG_FILE" 2>/dev/null && USB_SCORE=$((USB_SCORE + 1))
grep -q "CONFIG_USB_U_ETHER=y" "$DEFCONFIG_FILE" 2>/dev/null && USB_SCORE=$((USB_SCORE + 1))

echo "USB Arsenal: $USB_SCORE/8"
```

**Note:** Informational only — does not affect readiness score.

---

## Capability 11: Driver Coverage Audit

**Category:** INFORMATIONAL

**Purpose:** Evaluate kernel subsystem coverage.

**Two-Phase Evaluation:**

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

**How to Run:**

```bash
echo "=== Driver Coverage Audit ==="
DEFCONFIG_FILE=$(ls arch/*/configs/*_defconfig 2>/dev/null | head -1)

# Phase 1: Source Coverage
echo "Source Coverage:"
DRV_SRC=0
[ -d "drivers/usb" ] && echo "[✓] USB" && DRV_SRC=$((DRV_SRC + 1)) || echo "[ ] USB"
[ -d "drivers/net/wireless" ] && echo "[✓] WiFi" && DRV_SRC=$((DRV_SRC + 1)) || echo "[ ] WiFi"
[ -d "drivers/bluetooth" ] && echo "[✓] Bluetooth" && DRV_SRC=$((DRV_SRC + 1)) || echo "[ ] Bluetooth"
[ -d "drivers/hid" ] && echo "[✓] HID" && DRV_SRC=$((DRV_SRC + 1)) || echo "[ ] HID"
[ -d "drivers/media" ] && echo "[✓] Media" && DRV_SRC=$((DRV_SRC + 1)) || echo "[ ] Media"
[ -d "drivers/iio" ] && echo "[✓] Sensors" && DRV_SRC=$((DRV_SRC + 1)) || echo "[ ] Sensors"
echo "Source: $DRV_SRC/6"

# Phase 2: Config Coverage
echo ""
echo "Config Coverage:"
DRV_CFG=0
grep -q "CONFIG_USB=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
grep -q "CONFIG_USB_GADGET=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
grep -q "CONFIG_CFG80211=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
grep -q "CONFIG_MAC80211=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
grep -q "CONFIG_BT=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
grep -q "CONFIG_BT_HCIBTUSB=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
grep -q "CONFIG_HID=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
grep -q "CONFIG_USB_HID=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
grep -q "CONFIG_MEDIA_SUPPORT=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
grep -q "CONFIG_VIDEO_DEV=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
grep -q "CONFIG_IIO=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
grep -q "CONFIG_SENSORS=y" "$DEFCONFIG_FILE" 2>/dev/null && DRV_CFG=$((DRV_CFG + 1))
echo "Config: $DRV_CFG/12"

echo ""
echo "Driver Coverage: Source $DRV_SRC/6, Config $DRV_CFG/12"
```

**Note:** Informational only — does not affect readiness score.

---

## Capability 12: Security Audit

**Category:** MEDIUM

**Purpose:** Audit kernel security configuration.

**Checks:**

| Config | Description |
|--------|-------------|
| CONFIG_SECURITY | Security framework |
| CONFIG_SECURITY_SELINUX | SELinux |
| CONFIG_CC_STACKPROTECTOR | Stack protection |
| CONFIG_RANDOMIZE_BASE | KASLR |

**How to Run:**

```bash
echo "=== Security Audit ==="
SECURITY=0
DEFCONFIG_FILE=$(ls arch/*/configs/*_defconfig 2>/dev/null | head -1)

grep -q "CONFIG_SECURITY=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_SECURITY" && SECURITY=$((SECURITY + 2)) || echo "[ ] CONFIG_SECURITY"
grep -q "CONFIG_SECURITY_SELINUX=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_SECURITY_SELINUX" && SECURITY=$((SECURITY + 2)) || echo "[ ] CONFIG_SECURITY_SELINUX"
grep -q "CONFIG_CC_STACKPROTECTOR" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_CC_STACKPROTECTOR" && SECURITY=$((SECURITY + 2)) || echo "[ ] CONFIG_CC_STACKPROTECTOR"
grep -q "CONFIG_RANDOMIZE_BASE=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_RANDOMIZE_BASE" && SECURITY=$((SECURITY + 2)) || echo "[ ] CONFIG_RANDOMIZE_BASE"

echo "Security: $SECURITY/8"
```

**Score:** 8 points max

---

## Capability 13: Patch Conflict Detection

**Category:** MEDIUM

**Purpose:** Detect potential patch conflicts.

**Checks:**

| Check | Description |
|-------|-------------|
| .patch files | Patch files present |
| Conflict markers | Merge conflict markers |
| Modified files | Uncommitted modifications |

**How to Run:**

```bash
echo "=== Patch Conflict Detection ==="

PATCH_COUNT=$(find . -name "*.patch" 2>/dev/null | wc -l)
CONFLICT_MARKERS=$(grep -r "<<<<<<" . 2>/dev/null | wc -l || echo "0")
MODIFIED=$(git status --porcelain 2>/dev/null | wc -l)

echo "Patch files: $PATCH_COUNT"
[ "$CONFLICT_MARKERS" -gt 0 ] && echo "[!] Conflict markers: $CONFLICT_MARKERS" || echo "[✓] No conflict markers"
echo "Modified files: $MODIFIED"
```

**Score:** Informational

---

## Capability 14: Upstream Sync Readiness

**Category:** MEDIUM

**Purpose:** Prepare for upstream sync.

**Checks:**

| Check | Description |
|-------|-------------|
| Remote configured | upstream remote exists |
| Clean tree | No uncommitted changes |
| Branch status | On correct branch |

**How to Run:**

```bash
echo "=== Upstream Sync Readiness ==="

git remote get-url upstream >/dev/null 2>&1 && echo "[✓] Remote: upstream configured" || echo "[ ] Remote: upstream NOT configured"
[ -z "$(git status --porcelain)" ] && echo "[✓] Tree: clean" || echo "[ ] Tree: dirty"
BRANCH=$(git branch --show-current)
echo "Branch: $BRANCH"
```

**Score:** Informational

---

## Capability 15: Build Configuration Audit

**Category:** LOWER

**Purpose:** Validate kernel build configuration.

**Checks:**

| Config | Description |
|--------|-------------|
| CONFIG_LOCALVERSION | Local version |
| CONFIG_MODULES | Module support |
| CONFIG_SMP | SMP support |
| CONFIG_CMDLINE | Boot cmdline |

**How to Run:**

```bash
echo "=== Build Configuration Audit ==="
BUILD=0
DEFCONFIG_FILE=$(ls arch/*/configs/*_defconfig 2>/dev/null | head -1)

grep -q "CONFIG_LOCALVERSION=" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_LOCALVERSION" && BUILD=$((BUILD + 2)) || echo "[ ] CONFIG_LOCALVERSION"
grep -q "CONFIG_MODULES=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_MODULES" && BUILD=$((BUILD + 2)) || echo "[ ] CONFIG_MODULES"
grep -q "CONFIG_SMP=y" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_SMP" && BUILD=$((BUILD + 2)) || echo "[ ] CONFIG_SMP"
grep -q "CONFIG_CMDLINE" "$DEFCONFIG_FILE" 2>/dev/null && echo "[✓] CONFIG_CMDLINE" && BUILD=$((BUILD + 2)) || echo "[ ] CONFIG_CMDLINE"

echo "Build Config: $BUILD/8"
```

**Score:** 8 points max

---

## Capability 16: Release Readiness

**Category:** LOWER

**Purpose:** Verify kernel release readiness.

**Checks:**

| Check | Description |
|-------|-------------|
| CHANGELOG | Changelog present |
| VERSION | Version defined |
| README | Documentation present |

**How to Run:**

```bash
echo "=== Release Readiness ==="
RELEASE=0

[ -f "CHANGELOG.md" ] && echo "[✓] CHANGELOG.md" && RELEASE=$((RELEASE + 1)) || echo "[ ] CHANGELOG.md"
[ -f "VERSION" ] && echo "[✓] VERSION" && RELEASE=$((RELEASE + 1)) || echo "[ ] VERSION"
[ -f "README.md" ] && echo "[✓] README.md" && RELEASE=$((RELEASE + 1)) || echo "[ ] README.md"

echo "Release Readiness: $RELEASE/4"
```

**Score:** 4 points max

---

## Scoring Summary

### Kernel Readiness (100 points)

| Component | Points | Category |
|-----------|--------|----------|
| Kernel Health | 15 | CRITICAL |
| Defconfig | 16 | CRITICAL |
| Module | 12 | CRITICAL |
| Root Ecosystem | 10 | MEDIUM |
| Security | 8 | MEDIUM |
| Build Config | 8 | LOWER |
| Release Readiness | 4 | LOWER |
| **Total** | **73** | |

### Informational (not scored)

- GKI Audit
- NetHunter Readiness
- External WiFi Audit
- HID Gadget Audit
- ConfigFS Audit
- USB Arsenal Audit
- Driver Coverage Audit
- Patch Conflict Detection
- Upstream Sync Readiness

---

## Common Pitfalls

1. **KernelSU false positive** — Require uppercase KERNELSU + hooks
2. **GKI false negative** — Legacy kernels are valid
3. **WiFi config as module** — Check =y only
4. **Hard-fail over-triggering** — Only 3 critical components

---

## Verification Checklist

After running audit:

- [ ] Kernel Readiness score calculated
- [ ] Hard-fail logic applied if needed
- [ ] Informational audits completed
- [ ] Critical failures highlighted
- [ ] Recommendations provided
