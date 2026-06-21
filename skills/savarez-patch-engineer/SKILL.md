---
name: savarez-patch-engineer
description: "Patch engineering: build fixes, SELinux patches, HAL fixes, VINTF fixes, bootloop fixes, init.rc fixes, device tree patches, vendor blob analysis, kernel config, commit messages, risk assessment, rollback planning."
---

# Savarez Patch Engineer

Transform audit findings and debug results into actionable fixes and patch recommendations.

## Purpose

Convert root-cause analysis into concrete patches with risk assessment and rollback planning. This skill does not execute changes — it generates recommendations.

## Skill Type

- **Engineering-based** (not audit or diagnostic)
- **Fix generation** oriented
- **No automatic code modification**
- **Recommendation driven**

## When to Use

| Scenario | Use This Skill |
|----------|----------------|
| Build failure fix | ✅ |
| SELinux policy fix | ✅ |
| HAL crash fix | ✅ |
| Bootloop fix | ✅ |
| Kernel config fix | ✅ |
| ROM readiness check | Use savarez-android-rom-maintainer |
| Kernel health check | Use savarez-kernel-maintainer |
| Root cause analysis | Use savarez-debug-specialist |

## Capabilities

### 12 Capabilities

| # | Capability | Risk Level | Purpose |
|---|------------|------------|---------|
| 1 | Build Fix Generator | LOW-MEDIUM | Fix build failures |
| 2 | SELinux Patch Generator | MEDIUM | SELinux policy fixes |
| 3 | HAL Fix Recommendation | HIGH | HAL crash fixes |
| 4 | VINTF Compatibility Fix | MEDIUM | VINTF manifest fixes |
| 5 | Bootloop Fix Recommendation | HIGH | Bootloop fixes |
| 6 | Init.rc Fix Analysis | MEDIUM | Init script fixes |
| 7 | Device Tree Patch Analysis | MEDIUM | Device tree fixes |
| 8 | Vendor Blob Dependency Analysis | HIGH | Vendor blob issues |
| 9 | Kernel Config Patch Recommendation | LOW | Kernel config fixes |
| 10 | Commit Message Generator | LOW | Commit formatting |
| 11 | Patch Risk Assessment | — | Risk evaluation |
| 12 | Rollback Planning | — | Rollback strategies |

---

## Risk Model

| Level | Criteria | Approval |
|-------|----------|----------|
| LOW | 1-2 files, peripheral | Auto-approve |
| MEDIUM | 3-5 files, core | Review required |
| HIGH | 6-10 files, critical | Approval required |
| CRITICAL | 10+ files, system | Full review |

### Risk Factors

| Factor | Weight |
|--------|--------|
| File count | 25% |
| Component criticality | 25% |
| Change scope | 25% |
| Testing coverage | 25% |

---

## Rollback Requirement

| Risk Level | Rollback Plan Required |
|------------|------------------------|
| LOW | Optional |
| MEDIUM | Recommended |
| HIGH | **Required** |
| CRITICAL | **Required** |

---

## Output Format

Every capability produces:

```
=== Root Cause ===
[type]: [description]

=== Recommended Change ===
[action]: [details]

=== Affected Files ===
[list of files]

=== Example Diff ===
[diff snippet]

=== Risk Assessment ===
Level: [LOW/MEDIUM/HIGH/CRITICAL]
Scope: [component]
Testing: [requirements]

=== Validation Plan ===
1. [step 1]
2. [step 2]
3. [step 3]

=== Rollback Plan ===
[if HIGH or CRITICAL]
Trigger: [conditions]
Procedure: [steps]
Backup: [tag/location]
```

---

## SELinux Capability Restriction

**IMPORTANT:** SELinux Patch Generator follows strict guidelines:

1. **Never assume every AVC denial requires an allow rule**
2. **Always include alternative root-cause possibilities:**
   - Denial may be expected (informational)
   - Denial may indicate misconfigured domain
   - Denial may require type transition, not allow
   - Denial may be symptom of larger issue
3. **Prefer minimal policy recommendations**
4. **Always recommend testing in permissive mode first**

---

## Reference Files

| File | Purpose |
|------|---------|
| build-fix.md | Build error fixes |
| selinux-patch.md | SELinux policy patches |
| hal-fix.md | HAL crash fixes |
| vintf-fix.md | VINTF compatibility |
| bootloop-fix.md | Bootloop fixes |
| init-rc-fix.md | Init script fixes |
| device-tree-patch.md | Device tree patches |
| vendor-blob-analysis.md | Vendor dependencies |
| kernel-config-patch.md | Kernel config fixes |
| commit-message.md | Commit message format |
| risk-assessment.md | Risk evaluation |
| rollback-planning.md | Rollback strategies |

---

## Separation from Other Skills

### vs Audit Skills

| Audit Skills | Patch Engineer |
|--------------|----------------|
| Check readiness | Generate fixes |
| Score 0-100 | Risk assessment |
| Pass/Fail | Patches + rollback |

### vs Debug Specialist

| Debug Specialist | Patch Engineer |
|------------------|----------------|
| Find root cause | Generate fix |
| Analyze logs | Create patches |
| Identify issue | Assess risk |

### Workflow

```
Audit Skills → Debug Specialist → Patch Engineer → Release
发现问题      分析问题            修复问题         发布
```

---

## Example Output

```
=== Patch Engineer Analysis ===

Input: SELinux denial log
Mode: SELinux Patch Generator

=== Root Cause ===
Type: Missing SELinux policy rule
Source: camera_server
Target: camera_device
Permission: read

=== Alternative Root Causes ===
1. Expected denial (informational only)
2. Misconfigured camera_server domain
3. Missing type transition rule

=== Recommended Change ===
Add minimal allow rule to device sepolicy

=== Affected Files ===
device/xiaomi/onyx/sepolicy/camera_server.te

=== Example Diff ===
+allow camera_server camera_device:dir read;
+allow camera_server camera_device:file { open read getattr };

=== Risk Assessment ===
Level: MEDIUM
Scope: Camera HAL
Testing: Camera functionality test

=== Validation Plan ===
1. Build with new policy
2. Boot to system
3. Test camera functionality
4. Verify no new denials

=== Rollback Plan ===
Trigger: Camera not working
Procedure: Revert sepolicy change
Backup: Pre-change tag available
```

---

## Notes

- All outputs are recommendations, not automatic changes
- Risk assessment is required for all patches
- Rollback planning is mandatory for HIGH/CRITICAL risks
- SELinux patches require alternative analysis
- Always verify backup before applying patches
