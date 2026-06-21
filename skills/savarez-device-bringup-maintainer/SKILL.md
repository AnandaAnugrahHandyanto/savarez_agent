---
name: savarez-device-bringup-maintainer
description: "Android device bring-up: identity, hardware ecosystem, boot chain, vendor integration, partition layout, HAL interfaces, recovery, SELinux, build/boot diagnostics."
---

# Savarez Device Bringup Maintainer

Android device bring-up workflow and first-boot readiness auditing.

## Purpose

Evaluate whether an Android device tree is ready for initial bring-up. Separate from ROM release readiness — this skill focuses on getting a device booting for the first time.

## When to Use

| Scenario | Use This Skill |
|----------|----------------|
| New device bring-up | ✅ |
| First boot issues | ✅ |
| Vendor tree validation | ✅ |
| ROM release readiness | Use savarez-android-rom-maintainer |
| Kernel compilation | Use savarez-kernel-maintainer |

## Capabilities

### Scored Capabilities (8)

| # | Capability | Category | Points |
|---|------------|----------|--------|
| 1 | Device Identity Audit | CRITICAL | 16 |
| 2 | Hardware Ecosystem Audit | CRITICAL | 15 |
| 3 | Boot Chain Audit | CRITICAL | 16 |
| 4 | Vendor Integration Audit | CRITICAL | 15 |
| 5 | Partition Layout Audit | MEDIUM | 16 |
| 6 | HAL & Interface Audit | MEDIUM | 15 |
| 7 | Recovery & Fastbootd Audit | MEDIUM | 16 |
| 8 | SELinux Bring-Up Audit | MEDIUM | 16 |

**Total Scored: 125 points**

### Informational Capabilities (2)

| # | Capability | Category |
|---|------------|----------|
| 9 | Build Error Diagnostics | LOWER |
| 10 | Boot Failure Diagnostics | LOWER |

### Scoring Capability (1)

| # | Capability | Purpose |
|---|------------|---------|
| 11 | Bring-Up Readiness Score | Calculate final score |

---

## Scoring Model

### Normalization

```bash
NORMALIZED=$((RAW_SCORE * 100 / 125))
```

### Category Thresholds

| Score | Category |
|-------|----------|
| 90-100 | READY |
| 70-89 | BETA |
| 50-69 | ALPHA |
| 25-49 | BRING-UP |
| 0-24 | NOT READY |

---

## Hard-Fail Logic

### Critical Components

| Component | Weight | Max Points |
|-----------|--------|------------|
| Device Identity | 12.8% | 16 |
| Hardware Ecosystem | 12.0% | 15 |
| Boot Chain | 12.8% | 16 |
| Vendor Integration | 12.0% | 15 |
| **Total Critical** | **49.6%** | **62** |

### Rules

| Failures | Max Score | Category |
|----------|-----------|----------|
| 0 | 100 | Normal |
| 1 | 49 | BRING-UP |
| 2 | 25 | NOT READY |
| 3+ | 10 | NOT READY |

### Implementation

```bash
FAIL_COUNT=0
[ "$IDENTITY" -eq 0 ] && FAIL_COUNT=$((FAIL_COUNT + 1))
[ "$HW" -eq 0 ] && FAIL_COUNT=$((FAIL_COUNT + 1))
[ "$BOOT" -eq 0 ] && FAIL_COUNT=$((FAIL_COUNT + 1))
[ "$VENDOR" -eq 0 ] && FAIL_COUNT=$((FAIL_COUNT + 1))

if [ "$FAIL_COUNT" -ge 3 ]; then
    FINAL=10; CATEGORY="NOT READY"
elif [ "$FAIL_COUNT" -ge 2 ]; then
    FINAL=25; CATEGORY="NOT READY"
elif [ "$FAIL_COUNT" -ge 1 ]; then
    FINAL=49; CATEGORY="BRING-UP"
else
    FINAL=$NORMALIZED
    if [ "$FINAL" -ge 90 ]; then
        CATEGORY="READY"
    elif [ "$FINAL" -ge 70 ]; then
        CATEGORY="BETA"
    elif [ "$FINAL" -ge 50 ]; then
        CATEGORY="ALPHA"
    else
        CATEGORY="BRING-UP"
    fi
fi
```

---

## Reference Files

| File | Purpose |
|------|---------|
| device-identity.md | Device identification checks |
| hardware-ecosystem.md | Hardware init and manifest |
| boot-chain.md | Boot configuration checks |
| vendor-integration.md | Vendor tree and blobs |
| partition-layout.md | Partition structure |
| hal-interface.md | HAL packages and interfaces |
| recovery-fastbootd.md | Recovery and fastboot |
| selinux-bringup.md | SELinux policy checks |
| build-error-diagnostics.md | Build error patterns |
| boot-failure-diagnostics.md | Boot failure patterns |

---

## Separation from Other Skills

### vs savarez-android-rom-maintainer

| ROM Maintainer | Device Bringup |
|----------------|----------------|
| ROM release readiness | Device bring-up workflow |
| OTA, changelogs | First boot readiness |
| Long-term maintenance | Initial bring-up |

### vs savarez-kernel-maintainer

| Kernel Maintainer | Device Bringup |
|-------------------|----------------|
| Kernel .config | Device tree |
| CONFIG_* audits | Hardware init |
| GKI, modules | Vendor integration |

---

## Example Output

```
=== Device Bring-Up Audit ===

Device: Poco F7 (onyx)
SoC: Qualcomm SM8635

=== Device Identity ===
[✓] Device codename: onyx
[✓] Board name: onyx
[✓] SoC family: Qualcomm
[✓] Android target: 15
Device Identity: 16/16

=== Hardware Ecosystem ===
[✓] Init scripts
[✓] Fstab config
[✓] Overlay config
[✓] Architecture
[✓] Device manifest
Hardware Ecosystem: 15/15

=== Boot Chain ===
[✓] Bootloader
[✓] Kernel image
[✓] Ramdisk
[✓] DTB/DTBO
Boot Chain: 16/16

=== Vendor Integration ===
[✓] Vendor Tree
[✓] Blob List (proprietary-files.txt)
[✓] Extraction Scripts (extract-files.sh)
[✓] Blob Presence
[✓] Vendor Overlays
Vendor Integration: 15/15

=== Partition Layout ===
[✓] System partition
[✓] Vendor partition
[✓] Product partition
[✓] Super partition
Partition Layout: 16/16

=== HAL & Interface ===
[✓] HAL packages
[✓] Vendor HAL dirs
[✓] PRODUCT_PACKAGES
[✓] HIDL/AIDL interfaces
[✓] HAL manifest
HAL & Interface: 15/15

=== Recovery & Fastbootd ===
[✓] Recovery config
[✓] Recovery resources
[✓] Fastboot support
[✓] Fastbootd support
Recovery & Fastbootd: 16/16

=== SELinux Bring-Up ===
[✓] SELinux policy
[✓] File contexts
[✓] Property contexts
[✓] Service contexts
SELinux Bring-Up: 16/16

=== Build Error Diagnostics (INFO) ===
[✓] No ninja failures
[✓] No soong failures
[✓] No missing dependencies
[✓] No missing blobs
[✓] No duplicate modules
[✓] No namespace conflicts
[✓] No VINTF errors
[✓] No SEPolicy errors
Build Errors: 0/8 (informational)

=== Boot Failure Diagnostics (INFO) ===
[✓] No bootloop
[✓] Not fastboot-only
[✓] Not recovery-only
[✓] Display working
[✓] system_server stable
[✓] No SELinux storm
[✓] No kernel panic
Boot Failures: 0/7 (informational)

=== Bring-Up Readiness ===
Critical Failures: 0
Raw Score: 125/125
Normalized: 100/100

Category: READY

=== Recommendations ===
1. Device is ready for bring-up
2. All critical components verified
3. Proceed with first boot test
```

---

## Audit Workflow

### Step 1: Identify Device

```bash
# Find device tree
find device/ -name "BoardConfig.mk" | head -1

# Extract codename
grep "PRODUCT_DEVICE" device/*/BoardConfig.mk | head -1
```

### Step 2: Run Scored Audits

Execute capabilities 1-8 in order.

### Step 3: Run Informational Diagnostics

Execute capabilities 9-10 if build output or device logs available.

### Step 4: Calculate Score

```bash
RAW_SCORE=$((IDENTITY + HW + BOOT + VENDOR + PART + HAL + REC + SELINUX))
NORMALIZED=$((RAW_SCORE * 100 / 125))
```

### Step 5: Apply Hard-Fail

Check critical component failures and apply score caps.

### Step 6: Generate Report

Output final readiness category and recommendations.

---

## Notes

- All checks are file-based (no runtime dependencies)
- Diagnostic capabilities (9-10) are informational only
- Hard-fail applies only to capabilities 1-4
- Vendor Integration is critical for first boot
- HAL presence affects hardware functionality
