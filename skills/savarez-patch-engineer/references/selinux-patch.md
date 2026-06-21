# SELinux Patch Generator Reference

## Purpose

Generate SELinux policy patches for denials.

## Inputs

- AVC denial log
- Source context
- Target context
- Permission

## Detection Logic

### Extract Denial Components

```bash
# Source context
grep "avc:.*denied" dmesg.txt | head -1 | \
    grep -o "scontext=[^ ]*" | cut -d= -f2

# Target context
grep "avc:.*denied" dmesg.txt | head -1 | \
    grep -o "tcontext=[^ ]*" | cut -d= -f2

# Permission
grep "avc:.*denied" dmesg.txt | head -1 | \
    grep -o "permission=[^ ]*" | cut -d= -f2
```

## Output Format

- Root cause: Missing SELinux policy
- Recommended change: Add allow rule
- Affected files: device/sepolicy/
- Example diff:
```diff
+allow source_domain target_domain:class permission;
```
- Risk level: MEDIUM

## IMPORTANT: Alternative Root Causes

**Never assume every AVC denial requires an allow rule.**

Always consider:

1. **Expected denial (informational)**
   - Denial may be normal operation
   - No fix required

2. **Misconfigured domain**
   - Source domain may be wrong
   - Fix domain assignment, not policy

3. **Type transition needed**
   - May need type_transition, not allow
   - Check for file creation contexts

4. **Larger issue indicator**
   - Denial may be symptom of broken service
   - Fix root cause, not symptom

## Risk Level Guidance

| Scenario | Risk |
|----------|------|
| Minimal allow rule | MEDIUM |
| Multiple rules | HIGH |
| Domain modification | HIGH |
| Policy rewrite | CRITICAL |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Overly permissive | Use minimal rule |
| Missing context | Verify domains |
| Breaking policy | Test in permissive |
| Expected denial | Check if informational |
