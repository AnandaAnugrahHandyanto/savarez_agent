---
name: savarez-android-rom-maintainer
description: "Android ROM maintenance: device tree, vendor, board config, SELinux, VINTF, kernel ecosystem, boot/recovery, build readiness, and bring-up diagnostics."
version: 1.0.0
author: Savarez Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [android, rom, lineage, kernel, selinux, vintf, bringup, nethunter, kernelsu]
    related_skills: [savarez-git-maintainer, savarez-release-manager]
---

# Savarez Android ROM Maintainer

## Overview

Comprehensive Android ROM maintenance skill.
Provides auditing, scoring, and diagnostics for ROM development.

Covers: LineageOS, Evolution X, PixelOS, NetHunter, KernelSU projects.
Supports: Android 14/15/16, GKI devices, Legacy devices, Virtual A/B.

## When to Use

- Before ROM build
- During device bring-up
- When debugging boot failures
- When auditing device tree
- When preparing release
- When checking NetHunter readiness

**Don't use for:**

- Generic git operations (use savarez-git-maintainer)
- Release management (use savarez-release-manager)
- Kernel compilation (out of scope)

---

## Capabilities Overview

| # | Capability | Category |
|---|------------|----------|
| 1 | Device Tree Audit | Core |
| 2 | Vendor Tree Audit | Core |
| 3 | Board Configuration Audit | Core |
| 4 | SELinux Audit | Core |
| 5 | API-Level Audit | Core |
| 6 | VINTF Audit | Core |
| 7 | Boot & Recovery Audit | Core |
| 8 | Kernel Ecosystem Audit | Core |
| 9 | Build Readiness Score | Scoring |
| 10 | Release Readiness Audit | Release |
| 11 | Bring-Up Diagnostic Assistant | Debug |
| 12 | NetHunter Readiness | Informational |

---

## Capability 1: Device Tree Audit

**Purpose:** Validate device tree structure.

**Checks:**

| Check | Description |
|-------|-------------|
| AndroidProducts.mk | Product definitions |
| BoardConfig.mk | Board configuration |
| device.mk | Device makefile |
| PRODUCT_NAME | Product name defined |
| PRODUCT_DEVICE | Device name defined |

**How to Run:**

```bash
echo "=== Device Tree Audit ==="
DT_SCORE=0

[ -f "AndroidProducts.mk" ] && echo "[✓] AndroidProducts.mk" && DT_SCORE=$((DT_SCORE + 3)) || echo "[ ] AndroidProducts.mk"
[ -f "BoardConfig.mk" ] && echo "[✓] BoardConfig.mk" && DT_SCORE=$((DT_SCORE + 3)) || echo "[ ] BoardConfig.mk"
[ -f "device.mk" ] && echo "[✓] device.mk" && DT_SCORE=$((DT_SCORE + 3)) || echo "[ ] device.mk"
grep -q "PRODUCT_NAME" AndroidProducts.mk 2>/dev/null && echo "[✓] PRODUCT_NAME" && DT_SCORE=$((DT_SCORE + 3)) || echo "[ ] PRODUCT_NAME"
grep -q "PRODUCT_DEVICE" device.mk 2>/dev/null && echo "[✓] PRODUCT_DEVICE" && DT_SCORE=$((DT_SCORE + 3)) || echo "[ ] PRODUCT_DEVICE"

echo "Device Tree: $DT_SCORE/15"
```

**Score:** 15 points max

---

## Capability 2: Vendor Tree Audit

**Purpose:** Validate vendor blob configuration.

**Checks:**

| Check | Description |
|-------|-------------|
| proprietary-files.txt | Blob list exists |
| Blob count | Sufficient blobs defined |
| extract-files.sh | Extraction script present |
| BOARD_VENDOR | Vendor defined |

**How to Run:**

```bash
echo "=== Vendor Tree Audit ==="
VT_SCORE=0

[ -f "proprietary-files.txt" ] && echo "[✓] proprietary-files.txt" && VT_SCORE=$((VT_SCORE + 5)) || echo "[ ] proprietary-files.txt"
BLOB_COUNT=$(grep -v "^#" proprietary-files.txt 2>/dev/null | grep -v "^$" | wc -l)
[ "$BLOB_COUNT" -gt 50 ] && echo "[✓] Blobs: $BLOB_COUNT" && VT_SCORE=$((VT_SCORE + 5)) || echo "[ ] Blobs: $BLOB_COUNT (need >50)"
[ -f "extract-files.sh" ] && echo "[✓] extract-files.sh" && VT_SCORE=$((VT_SCORE + 5)) || echo "[ ] extract-files.sh"

echo "Vendor Tree: $VT_SCORE/15"
```

**Score:** 15 points max

---

## Capability 3: Board Configuration Audit

**Purpose:** Validate BoardConfig.mk and related configurations.

**Includes:** Dynamic partitions, AVB, partition sizes, architecture.

**Checks:**

| Check | Description |
|-------|-------------|
| TARGET_KERNEL_SOURCE | Kernel source path |
| TARGET_KERNEL_CONFIG | Kernel config |
| TARGET_ARCH | Architecture |
| BOARD_SYSTEMIMAGE_PARTITION_SIZE | System partition |
| BOARD_SUPER_PARTITION_SIZE | Super partition |
| BOARD_SUPER_PARTITION_GROUPS | Dynamic partition groups |
| BOARD_AVB_ENABLE | AVB enabled |
| BOARD_AVB_ROLLBACK_INDEX | Rollback index |

**How to Run:**

```bash
echo "=== Board Configuration Audit ==="
BC_SCORE=0

grep -q "TARGET_KERNEL_SOURCE" BoardConfig.mk 2>/dev/null && echo "[✓] TARGET_KERNEL_SOURCE" && BC_SCORE=$((BC_SCORE + 2)) || echo "[ ] TARGET_KERNEL_SOURCE"
grep -q "TARGET_KERNEL_CONFIG" BoardConfig.mk 2>/dev/null && echo "[✓] TARGET_KERNEL_CONFIG" && BC_SCORE=$((BC_SCORE + 2)) || echo "[ ] TARGET_KERNEL_CONFIG"
grep -q "TARGET_ARCH" BoardConfig.mk 2>/dev/null && echo "[✓] TARGET_ARCH" && BC_SCORE=$((BC_SCORE + 2)) || echo "[ ] TARGET_ARCH"
grep -q "BOARD_SYSTEMIMAGE_PARTITION_SIZE" BoardConfig.mk 2>/dev/null && echo "[✓] SYSTEM_PARTITION" && BC_SCORE=$((BC_SCORE + 2)) || echo "[ ] SYSTEM_PARTITION"
grep -q "BOARD_SUPER_PARTITION_SIZE" BoardConfig.mk 2>/dev/null && echo "[✓] SUPER_PARTITION" && BC_SCORE=$((BC_SCORE + 2)) || echo "[ ] SUPER_PARTITION"
grep -q "BOARD_SUPER_PARTITION_GROUPS" BoardConfig.mk 2>/dev/null && echo "[✓] PARTITION_GROUPS" && BC_SCORE=$((BC_SCORE + 2)) || echo "[ ] PARTITION_GROUPS"
grep -q "BOARD_AVB_ENABLE" BoardConfig.mk 2>/dev/null && echo "[✓] AVB_ENABLE" && BC_SCORE=$((BC_SCORE + 1)) || echo "[ ] AVB_ENABLE"
grep -q "BOARD_AVB_ROLLBACK_INDEX" BoardConfig.mk 2>/dev/null && echo "[✓] AVB_ROLLBACK" && BC_SCORE=$((BC_SCORE + 1)) || echo "[ ] AVB_ROLLBACK"

echo "Board Config: $BC_SCORE/14"
```

**Score:** 14 points max

---

## Capability 4: SELinux Audit

**Purpose:** Validate SELinux policy configuration.

**Checks:**

| Check | Description |
|-------|-------------|
| sepolicy/ directory | Policy directory exists |
| Permissive domains | No permissive domains |
| file_contexts | File contexts defined |
| device.te | Device policy present |

**How to Run:**

```bash
echo "=== SELinux Audit ==="
SE_SCORE=0

[ -d "sepolicy" ] && echo "[✓] sepolicy/ exists" && SE_SCORE=$((SE_SCORE + 3)) || echo "[ ] sepolicy/ missing"
PERMISSIVE=$(grep -r "permissive" sepolicy/ 2>/dev/null | grep -v "^#" | wc -l)
[ "$PERMISSIVE" -eq 0 ] && echo "[✓] No permissive domains" && SE_SCORE=$((SE_SCORE + 3)) || echo "[ ] Permissive domains: $PERMISSIVE"
[ -f "sepolicy/file_contexts" ] && echo "[✓] file_contexts" && SE_SCORE=$((SE_SCORE + 2)) || echo "[ ] file_contexts"

echo "SELinux: $SE_SCORE/8"
```

**Score:** 8 points max

---

## Capability 5: API-Level Audit

**Purpose:** Validate Android API level configuration.

**Detection Sources:**

| Source | Priority |
|--------|----------|
| PRODUCT_SHIPPING_API_LEVEL | HIGH |
| BOARD_SHIPPING_API_LEVEL | HIGH |
| BOARD_API_LEVEL | MEDIUM |
| PLATFORM_VERSION_LAST_STABLE | LOW |

**How to Run:**

```bash
echo "=== API-Level Audit ==="
API_SCORE=0

PRIMARY=$(grep "PRODUCT_SHIPPING_API_LEVEL" BoardConfig.mk 2>/dev/null | cut -d= -f2 | tr -d ' ')
BOARD=$(grep "BOARD_SHIPPING_API_LEVEL" BoardConfig.mk 2>/dev/null | cut -d= -f2 | tr -d ' ')
LEGACY=$(grep "BOARD_API_LEVEL" BoardConfig.mk 2>/dev/null | cut -d= -f2 | tr -d ' ')

if [ -n "$PRIMARY" ]; then
    EFFECTIVE="$PRIMARY"
    SOURCE="PRODUCT_SHIPPING_API_LEVEL"
    CONFIDENCE="HIGH"
elif [ -n "$BOARD" ]; then
    EFFECTIVE="$BOARD"
    SOURCE="BOARD_SHIPPING_API_LEVEL"
    CONFIDENCE="HIGH"
elif [ -n "$LEGACY" ]; then
    EFFECTIVE="$LEGACY"
    SOURCE="BOARD_API_LEVEL"
    CONFIDENCE="MEDIUM"
else
    EFFECTIVE="UNKNOWN"
    SOURCE="NONE"
    CONFIDENCE="NONE"
fi

[ -n "$PRIMARY" ] && echo "[✓] PRODUCT_SHIPPING_API_LEVEL: $PRIMARY" && API_SCORE=$((API_SCORE + 2)) || echo "[ ] PRODUCT_SHIPPING_API_LEVEL: MISSING"
[ -n "$BOARD" ] || [ -n "$LEGACY" ] && echo "[✓] Board API level: PRESENT" && API_SCORE=$((API_SCORE + 2)) || echo "[ ] Board API level: MISSING"
grep -q "PLATFORM_SECURITY_PATCH" BoardConfig.mk 2>/dev/null && echo "[✓] SECURITY_PATCH" && API_SCORE=$((API_SCORE + 1)) || echo "[ ] SECURITY_PATCH"

echo "API-Level: $API_SCORE/5 (Source: $SOURCE, Confidence: $CONFIDENCE)"
```

**Score:** 5 points max

---

## Capability 6: VINTF Audit

**Purpose:** Validate VINTF manifest and compatibility matrix.

**Checks:**

| Check | Description |
|-------|-------------|
| manifest.xml | Vendor manifest exists |
| compatibility_matrix.xml | Framework matrix exists |
| HAL count | Sufficient HALs declared |

**How to Run:**

```bash
echo "=== VINTF Audit ==="
VINTF_SCORE=0

[ -f "manifest.xml" ] && echo "[✓] manifest.xml" && VINTF_SCORE=$((VINTF_SCORE + 5)) || echo "[ ] manifest.xml"
[ -f "compatibility_matrix.xml" ] && echo "[✓] compatibility_matrix.xml" && VINTF_SCORE=$((VINTF_SCORE + 5)) || echo "[ ] compatibility_matrix.xml"
HAL_COUNT=$(grep -c "<hal" manifest.xml 2>/dev/null || echo "0")
[ "$HAL_COUNT" -gt 20 ] && echo "[✓] HAL declarations: $HAL_COUNT" && VINTF_SCORE=$((VINTF_SCORE + 5)) || echo "[ ] HAL declarations: $HAL_COUNT (need >20)"

echo "VINTF: $VINTF_SCORE/15"
```

**Score:** 15 points max

---

## Capability 7: Boot & Recovery Audit

**Purpose:** Validate boot layout and recovery configuration.

**Boot Layout Detection:**

| Layout | Indicators |
|--------|------------|
| Legacy | boot.img only, no A/B |
| A/B | AB_OTA_PARTITIONS defined |
| Virtual A/B | AB_OTA + snapshot + merge |
| GKI | init_boot + vendor_boot |

**Recovery Checks:**

| Check | Description |
|-------|-------------|
| recovery.fstab | Recovery fstab present |
| init.recovery.rc | Recovery init script |
| fastbootd | Fastbootd support |
| Dynamic partitions | Dynamic partition support |

**How to Run:**

```bash
echo "=== Boot & Recovery Audit ==="
BOOT_SCORE=0

# Boot layout detection
HAS_INIT_BOOT=$(grep -q "BOARD_INIT_BOOT_IMAGE_PARTITION_SIZE" BoardConfig.mk 2>/dev/null && echo "yes" || echo "no")
HAS_VENDOR_BOOT=$(grep -q "BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE" BoardConfig.mk 2>/dev/null && echo "yes" || echo "no")
HAS_AB=$(grep -q "AB_OTA_PARTITIONS" BoardConfig.mk 2>/dev/null && echo "yes" || echo "no")
HAS_SNAPSHOT=$(grep -q "BOARD_USES_RECOVERY_UPDATE\|BOARD_PREBUILT_BOOTIMAGE\|SNAPSHOT_UPDATE" BoardConfig.mk 2>/dev/null && echo "yes" || echo "no")

if [ "$HAS_INIT_BOOT" = "yes" ] && [ "$HAS_VENDOR_BOOT" = "yes" ]; then
    LAYOUT="GKI"
elif [ "$HAS_SNAPSHOT" = "yes" ] && [ "$HAS_AB" = "yes" ]; then
    LAYOUT="Virtual A/B"
elif [ "$HAS_AB" = "yes" ]; then
    LAYOUT="A/B"
else
    LAYOUT="Legacy"
fi

echo "Boot Layout: $LAYOUT"

# Boot components
grep -q "BOARD_BOOTIMAGE_PARTITION_SIZE" BoardConfig.mk 2>/dev/null && echo "[✓] boot.img" && BOOT_SCORE=$((BOOT_SCORE + 2)) || echo "[ ] boot.img"
[ "$HAS_INIT_BOOT" = "yes" ] && echo "[✓] init_boot.img" && BOOT_SCORE=$((BOOT_SCORE + 2)) || echo "[ ] init_boot.img"
[ "$HAS_VENDOR_BOOT" = "yes" ] && echo "[✓] vendor_boot.img" && BOOT_SCORE=$((BOOT_SCORE + 2)) || echo "[ ] vendor_boot.img"

# Recovery
[ -f "recovery.fstab" ] && echo "[✓] recovery.fstab" && BOOT_SCORE=$((BOOT_SCORE + 2)) || echo "[ ] recovery.fstab"
[ -f "init.recovery.rc" ] && echo "[✓] init.recovery.rc" && BOOT_SCORE=$((BOOT_SCORE + 2)) || echo "[ ] init.recovery.rc"
grep -q "fastbootd" BoardConfig.mk 2>/dev/null && echo "[✓] fastbootd" && BOOT_SCORE=$((BOOT_SCORE + 1)) || echo "[ ] fastbootd"
grep -q "BOARD_DYNAMIC_PARTITION_ENABLE" BoardConfig.mk 2>/dev/null && echo "[✓] Dynamic partitions" && BOOT_SCORE=$((BOOT_SCORE + 1)) || echo "[ ] Dynamic partitions"

echo "Boot & Recovery: $BOOT_SCORE/12"
```

**Score:** 12 points max

---

## Capability 8: Kernel Ecosystem Audit

**Purpose:** Validate kernel integration, model, DTBO, and root frameworks.

**Kernel Model Detection:**

| Model | Indicators |
|-------|------------|
| Legacy | TARGET_KERNEL_SOURCE only |
| GKI | GKI_KERNEL_VERSION or prebuilt |
| Hybrid | Both source and prebuilt |

**DTBO Detection:**

| Source | Description |
|--------|-------------|
| Prebuilt | BOARD_PREBUILT_DTBOIMAGE |
| Kernel-built | TARGET_DTBO_CFG defined |

**KernelSU Detection:**

| Framework | Detection |
|-----------|-----------|
| KernelSU | KERNELSU (uppercase) + hooks |
| KernelSU Next | KERNELSU + NEXT indicators |
| SUSFS | SUSFS references |
| None | No indicators |

**How to Run:**

```bash
echo "=== Kernel Ecosystem Audit ==="
KRN_SCORE=0

# Kernel integration
grep -q "TARGET_KERNEL_SOURCE" BoardConfig.mk 2>/dev/null && echo "[✓] TARGET_KERNEL_SOURCE" && KRN_SCORE=$((KRN_SCORE + 3)) || echo "[ ] TARGET_KERNEL_SOURCE"
grep -q "TARGET_KERNEL_CONFIG" BoardConfig.mk 2>/dev/null && echo "[✓] TARGET_KERNEL_CONFIG" && KRN_SCORE=$((KRN_SCORE + 3)) || echo "[ ] TARGET_KERNEL_CONFIG"
grep -q "BOARD_KERNEL_CMDLINE" BoardConfig.mk 2>/dev/null && echo "[✓] BOARD_KERNEL_CMDLINE" && KRN_SCORE=$((KRN_SCORE + 2)) || echo "[ ] BOARD_KERNEL_CMDLINE"

# Kernel model
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
grep -q "GKI_KERNEL_VERSION\|TARGET_PREBUILT_KERNEL" BoardConfig.mk 2>/dev/null && KRN_SCORE=$((KRN_SCORE + 1)) || true

# DTBO
DTBO_PREBUILT=$(grep "BOARD_PREBUILT_DTBOIMAGE" BoardConfig.mk 2>/dev/null | cut -d= -f2 | tr -d ' ')
DTBO_CFG=$(grep "TARGET_DTBO_CFG" BoardConfig.mk 2>/dev/null | cut -d= -f2 | tr -d ' ')

[ -n "$DTBO_PREBUILT" ] && echo "[✓] DTBO prebuilt: $DTBO_PREBUILT" && KRN_SCORE=$((KRN_SCORE + 1)) || echo "[ ] DTBO prebuilt: MISSING"
[ -n "$DTBO_CFG" ] && echo "[✓] DTBO config: $DTBO_CFG" && KRN_SCORE=$((KRN_SCORE + 1)) || echo "[ ] DTBO config: MISSING"

if [ -n "$DTBO_PREBUILT" ] || [ -n "$DTBO_CFG" ]; then
    echo "DTBO Status: READY"
elif grep -q "dtbo" BoardConfig.mk 2>/dev/null; then
    echo "DTBO Status: PARTIAL"
    KRN_SCORE=$((KRN_SCORE + 1))
else
    echo "DTBO Status: MISSING"
fi

# KernelSU (improved detection)
KSU_UPPER=$(grep -c "KERNELSU" kernel/ 2>/dev/null || echo "0")
KSU_HOOKS=$(grep -c "ksu_hook\|allow_su\|ksu_handle" kernel/ 2>/dev/null || echo "0")
SUSFS=$(grep -c "SUSFS\|susfs" kernel/ 2>/dev/null || echo "0")

if [ "$KSU_UPPER" -gt 2 ] && [ "$KSU_HOOKS" -gt 0 ]; then
    if grep -q "KSU_NEXT\|ksu_next" kernel/ 2>/dev/null; then
        KSU_FRAMEWORK="KernelSU Next"
    else
        KSU_FRAMEWORK="KernelSU"
    fi
elif [ "$KSU_UPPER" -gt 0 ]; then
    KSU_FRAMEWORK="KernelSU (partial)"
else
    KSU_FRAMEWORK="None"
fi

[ "$SUSFS" -gt 0 ] && SUSFS_STATUS="Present" || SUSFS_STATUS="Missing"

echo "Root Framework: $KSU_FRAMEWORK"
echo "SUSFS: $SUSFS_STATUS"

echo "Kernel Ecosystem: $KRN_SCORE/16"
```

**Score:** 16 points max

---

## Capability 9: Build Readiness Score

**Purpose:** Score ROM build readiness with hard-fail logic.

**Scoring Components:**

| Component | Weight | Max Points | Category |
|-----------|--------|------------|----------|
| Kernel Ecosystem | 16% | 16 | CRITICAL |
| VINTF | 15% | 15 | CRITICAL |
| Vendor Tree | 15% | 15 | CRITICAL |
| Device Tree | 15% | 15 | MEDIUM |
| Board Config | 14% | 14 | MEDIUM |
| Boot & Recovery | 12% | 12 | MEDIUM |
| SELinux | 8% | 8 | MEDIUM |
| API-Level | 5% | 5 | LOWER |
| **Total** | **100%** | **100** | |

**Hard-Fail Logic:**

| Failures | Max Score | Category |
|----------|-----------|----------|
| 0 | 100 | Normal |
| 1 | 49 | BRING-UP |
| 2 | 25 | BRING-UP |
| 3 | 10 | NOT READY |

**How to Run:**

```bash
echo "=== Build Readiness Score ==="

# Calculate component scores (from capabilities 1-8)
# ... (component calculations)

TOTAL=$((DT_SCORE + VT_SCORE + BC_SCORE + SE_SCORE + API_SCORE + VINTF_SCORE + BOOT_SCORE + KRN_SCORE))

# Hard-fail check
FAIL_COUNT=0
[ "$KRN_SCORE" -eq 0 ] && FAIL_COUNT=$((FAIL_COUNT + 1))
[ "$VINTF_SCORE" -eq 0 ] && FAIL_COUNT=$((FAIL_COUNT + 1))
[ "$VT_SCORE" -eq 0 ] && FAIL_COUNT=$((FAIL_COUNT + 1))

if [ "$FAIL_COUNT" -ge 3 ]; then
    MAX_SCORE=10
    CATEGORY="NOT READY"
    HARD_FAIL="YES"
elif [ "$FAIL_COUNT" -ge 2 ]; then
    MAX_SCORE=25
    CATEGORY="BRING-UP"
    HARD_FAIL="YES"
elif [ "$FAIL_COUNT" -ge 1 ]; then
    MAX_SCORE=49
    CATEGORY="BRING-UP"
    HARD_FAIL="YES"
else
    HARD_FAIL="NO"
    if [ "$TOTAL" -ge 90 ]; then
        CATEGORY="RELEASE READY"
    elif [ "$TOTAL" -ge 70 ]; then
        CATEGORY="STABLE"
    elif [ "$TOTAL" -ge 50 ]; then
        CATEGORY="BETA"
    elif [ "$TOTAL" -ge 30 ]; then
        CATEGORY="BRING-UP"
    else
        CATEGORY="NOT READY"
    fi
    MAX_SCORE=$TOTAL
fi

if [ "$HARD_FAIL" = "YES" ]; then
    echo ""
    echo "⚠️  HARD-FAIL TRIGGERED"
    echo "Critical component failures: $FAIL_COUNT"
    echo "Maximum ROM Readiness: $MAX_SCORE/100"
fi

echo ""
echo "ROM Readiness: $MAX_SCORE/100"
echo "Category: $CATEGORY"
```

**Output:** 0-100 score with category

---

## Capability 10: Release Readiness Audit

**Purpose:** Verify release readiness.

**Checks:**

| Check | Description |
|-------|-------------|
| CHANGELOG.md | Changelog present |
| ROM zip | Build artifact present |
| README.md | Documentation present |
| INSTALL.md | Install guide present |

**How to Run:**

```bash
echo "=== Release Readiness ==="
REL_SCORE=0

[ -f "CHANGELOG.md" ] && echo "[✓] CHANGELOG.md" && REL_SCORE=$((REL_SCORE + 1)) || echo "[ ] CHANGELOG.md"
find . -name "*.zip" -o -name "lineage-*.zip" 2>/dev/null | head -1 | grep -q ".zip" && echo "[✓] ROM zip" && REL_SCORE=$((REL_SCORE + 1)) || echo "[ ] ROM zip"
[ -f "README.md" ] && echo "[✓] README.md" && REL_SCORE=$((REL_SCORE + 1)) || echo "[ ] README.md"
[ -f "INSTALL.md" ] && echo "[✓] INSTALL.md" && REL_SCORE=$((REL_SCORE + 1)) || echo "[ ] INSTALL.md"

echo "Release Readiness: $REL_SCORE/4"
```

**Score:** 4 points (informational)

---

## Capability 11: Bring-Up Diagnostic Assistant

**Purpose:** Analyze common build/boot failures.

**Diagnostic Categories:**

| Category | Patterns |
|----------|----------|
| Build failures | Missing deps, kernel errors, SELinux |
| Boot failures | Kernel panic, init crash, zygote |
| Logcat patterns | ANR, crash, permission denied |
| Kernel issues | Panic, oops, driver failure |

**How to Run:**

```bash
echo "=== Bring-Up Diagnostics ==="

# Build analysis
echo "Build Analysis:"
grep -r "No rule to make target" . 2>/dev/null | head -3 && echo "  → Missing Makefile rule"
grep -r "Permission denied" . 2>/dev/null | head -3 && echo "  → Permission error"
grep -r "SELinux: denied" . 2>/dev/null | head -3 && echo "  → SELinux denial"

# Boot analysis
echo "Boot Analysis:"
grep -r "kernel panic" . 2>/dev/null | head -3 && echo "  → Kernel panic"
grep -r "init: Service.*restarting" . 2>/dev/null | head -3 && echo "  → Init service loop"
grep -r "Zygote.*died" . 2>/dev/null | head -3 && echo "  → Zygote crash"
```

**Output:** Diagnostic findings

---

## Capability 12: NetHunter Readiness

**Purpose:** Audit NetHunter-specific requirements (informational only).

**Required Configs (scored):**

| Config | Description |
|--------|-------------|
| CONFIG_USB_CONFIGFS | USB gadget core |
| CONFIG_USB_CONFIGFS_F_HID | HID gadget |
| CONFIG_USB_CONFIGFS_RNDIS | RNDIS network |
| CONFIG_CFG80211 | WiFi core |
| CONFIG_MAC80211 | WiFi mac |
| CONFIG_PACKET | Raw packet |

**Informational Configs (not scored):**

| Config | Description |
|--------|-------------|
| CONFIG_USB_CONFIGFS_ECM | ECM network |
| CONFIG_USB_CONFIGFS_NCM | NCM network |
| CONFIG_BT_HCIBTUSB | Bluetooth USB |

**How to Run:**

```bash
echo "=== NetHunter Readiness ==="
NH_SCORE=0
NH_TOTAL=6

# Required configs (scored)
grep -q "CONFIG_USB_CONFIGFS=y" .config 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_USB_CONFIGFS"
grep -q "CONFIG_USB_CONFIGFS_F_HID=y" .config 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS_F_HID" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_USB_CONFIGFS_F_HID"
grep -q "CONFIG_USB_CONFIGFS_RNDIS=y" .config 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS_RNDIS" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_USB_CONFIGFS_RNDIS"
grep -q "CONFIG_CFG80211=y" .config 2>/dev/null && echo "[✓] CONFIG_CFG80211" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_CFG80211"
grep -q "CONFIG_MAC80211=y" .config 2>/dev/null && echo "[✓] CONFIG_MAC80211" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_MAC80211"
grep -q "CONFIG_PACKET=y" .config 2>/dev/null && echo "[✓] CONFIG_PACKET" && NH_SCORE=$((NH_SCORE + 1)) || echo "[ ] CONFIG_PACKET"

# Informational (not scored)
echo ""
echo "Informational:"
grep -q "CONFIG_USB_CONFIGFS_ECM=y" .config 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS_ECM" || echo "[ ] CONFIG_USB_CONFIGFS_ECM"
grep -q "CONFIG_USB_CONFIGFS_NCM=y" .config 2>/dev/null && echo "[✓] CONFIG_USB_CONFIGFS_NCM" || echo "[ ] CONFIG_USB_CONFIGFS_NCM"
grep -q "CONFIG_BT_HCIBTUSB=y" .config 2>/dev/null && echo "[✓] CONFIG_BT_HCIBTUSB" || echo "[ ] CONFIG_BT_HCIBTUSB"

PERCENT=$((NH_SCORE * 100 / NH_TOTAL))
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

**Score:** 0-100 (informational, independent)

---

## Scoring Summary

### ROM Readiness (100 points)

| Component | Points | Category |
|-----------|--------|----------|
| Kernel Ecosystem | 16 | CRITICAL |
| VINTF | 15 | CRITICAL |
| Vendor Tree | 15 | CRITICAL |
| Device Tree | 15 | MEDIUM |
| Board Config | 14 | MEDIUM |
| Boot & Recovery | 12 | MEDIUM |
| SELinux | 8 | MEDIUM |
| API-Level | 5 | LOWER |
| **Total** | **100** | |

### NetHunter Readiness (100 points, informational)

| Config | Points |
|--------|--------|
| CONFIG_USB_CONFIGFS | 16.67 |
| CONFIG_USB_CONFIGFS_F_HID | 16.67 |
| CONFIG_USB_CONFIGFS_RNDIS | 16.67 |
| CONFIG_CFG80211 | 16.67 |
| CONFIG_MAC80211 | 16.67 |
| CONFIG_PACKET | 16.67 |
| **Total** | **100** |

---

## Common Pitfalls

1. **DTBO false positive** — Check for prebuilt OR config, not just one
2. **KernelSU false positive** — Require uppercase KERNELSU + hooks
3. **Virtual A/B detection** — Check multiple indicators
4. **NetHunter scoring** — Only required configs affect score

---

## Verification Checklist

After running audit:

- [ ] ROM Readiness score calculated
- [ ] Hard-fail logic applied if needed
- [ ] NetHunter score calculated independently
- [ ] Critical failures highlighted
- [ ] Recommendations provided
