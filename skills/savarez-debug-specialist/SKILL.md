---
name: savarez-debug-specialist
description: "Android debugging: logcat analysis, dmesg, kernel panic, tombstone, bootloop, recovery, fastboot, SELinux, VINTF, HAL, service crash, build failure root-cause."
---

# Savarez Debug Specialist

Systematic Android ROM and kernel debugging capabilities.

## Purpose

Provide root-cause analysis for Android failures. Unlike audit skills that check readiness, this skill analyzes symptoms to find causes.

## Skill Type

- **Diagnostic-based** (not audit-based)
- **No readiness scoring**
- **No hard-fail logic**
- **Root-cause analysis oriented**

## When to Use

| Scenario | Use This Skill |
|----------|----------------|
| Logcat errors | ✅ |
| Kernel panic | ✅ |
| Boot loop | ✅ |
| System crash | ✅ |
| Build failure | ✅ |
| SELinux denials | ✅ |
| ROM readiness | Use savarez-android-rom-maintainer |
| Kernel readiness | Use savarez-kernel-maintainer |
| Device bring-up | Use savarez-device-bringup-maintainer |

## Capabilities

### 12 Capabilities

| # | Capability | Priority | Purpose |
|---|------------|----------|---------|
| 1 | Logcat Analysis | MEDIUM | Parse logcat errors |
| 2 | Dmesg Analysis | MEDIUM | Kernel log analysis |
| 3 | Kernel Panic Analysis | CRITICAL | Panic root-cause |
| 4 | Tombstone Analysis | HIGH | Native crash analysis |
| 5 | Bootloop Diagnostics | CRITICAL | Boot loop root-cause |
| 6 | Recovery-Only Diagnostics | HIGH | Recovery-only root-cause |
| 7 | Fastboot-Only Diagnostics | HIGH | Fastboot-only root-cause |
| 8 | SELinux Denial Analysis | MEDIUM | SELinux policy issues |
| 9 | VINTF Failure Analysis | HIGH | VINTF manifest errors |
| 10 | HAL Failure Analysis | HIGH | HAL crash analysis |
| 11 | Service Crash Analysis | HIGH | Service crash analysis |
| 12 | Build Failure Root-Cause | MEDIUM | Build error analysis |

---

## Confidence Model

| Level | Criteria |
|-------|----------|
| CONFIRMED | Root cause identified with evidence |
| PROBABLE | Likely root cause, needs verification |
| POSSIBLE | Multiple candidates, needs investigation |
| UNKNOWN | Insufficient data |

## Priority Model

| Priority | Criteria |
|----------|----------|
| CRITICAL | System crash, boot failure |
| HIGH | Service crash, HAL failure |
| MEDIUM | SELinux denial, VINTF error |
| LOW | Warning, informational |

---

## Diagnostic Workflow

### Step 1: Identify Symptom

```bash
# Determine failure type
- Boot failure?
- System crash?
- Service crash?
- Build failure?
```

### Step 2: Gather Input

```bash
# Collect relevant logs
- logcat.txt
- dmesg.txt
- panic.log
- tombstone files
- build.log
```

### Step 3: Run Diagnostic

```bash
# Execute appropriate capability
- Analyze logs
- Parse patterns
- Extract errors
```

### Step 4: Identify Root Cause

```bash
# Determine cause
- Error type
- Faulting component
- Contributing factors
```

### Step 5: Generate Fix

```bash
# Recommend actions
- Code changes
- Configuration changes
- Clean flash
- Rebuild
```

---

## Reference Files

| File | Purpose |
|------|---------|
| logcat-analysis.md | Logcat parsing patterns |
| dmesg-analysis.md | Kernel log analysis |
| kernel-panic.md | Panic root-cause |
| tombstone-analysis.md | Native crash analysis |
| bootloop-diagnostics.md | Boot loop root-cause |
| recovery-diagnostics.md | Recovery-only root-cause |
| fastboot-diagnostics.md | Fastboot-only root-cause |
| selinux-denial.md | SELinux analysis |
| vintf-failure.md | VINTF error analysis |
| hal-failure.md | HAL crash analysis |
| service-crash.md | Service crash analysis |
| build-failure.md | Build error root-cause |

---

## Separation from Other Skills

### vs Audit Skills

| Audit Skills | Debug Specialist |
|--------------|------------------|
| Check readiness | Find root cause |
| Score 0-100 | No scoring |
| Pass/Fail | Root cause + fix |
| Prevent issues | Fix issues |

### Specific Separation

| Skill | Focus |
|-------|-------|
| ROM Maintainer | "Is this ROM build-ready?" |
| Kernel Maintainer | "Is this kernel healthy?" |
| Device Bringup | "Is this device ready?" |
| Release Manager | "Is this release ready?" |
| **Debug Specialist** | **"Why did this fail?"** |

---

## Example Output

```
=== Debug Specialist Analysis ===

Input: bootloop_logcat.txt
Mode: Bootloop Diagnostics

=== Boot Phase Analysis ===
[✓] Boot started
[✓] Zygote initialized
[✓] System server started
[✗] System server crashed

=== Root Cause ===
Type: System Server Crash
Component: ActivityManagerService
Error: java.lang.NullPointerException
Location: ActivityManagerService.java:1234

=== Recommended Fix ===
1. Check system partition integrity
2. Verify ActivityManagerService dependencies
3. Review recent system changes
4. Consider clean flash if persistent

=== Confidence ===
Level: CONFIRMED
Evidence: Stacktrace with file/line
```

---

## Notes

- All diagnostics are log-based (no runtime dependencies)
- Confidence levels help prioritize investigation
- Priority levels help triage issues
- Fix recommendations are guidance, not guarantees
- Always verify root cause before applying fixes
