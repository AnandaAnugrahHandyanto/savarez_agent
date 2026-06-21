# Security Patch Level Validator Reference

## Purpose

Validate security patch level is current.

## Inputs

- build.prop
- Security patch level

## Detection Logic

### Extract Patch Level

```bash
grep "ro.build.version.security_patch" build.prop
```

### Compare Against Expected

```bash
EXPECTED="2026-06-05"
CURRENT=$(grep "ro.build.version.security_patch" build.prop | cut -d= -f2)
```

### Calculate Age

```bash
# If older than 3 months: HIGH
# If older than 6 months: CRITICAL
```

## Output Format

- Current patch level
- Expected patch level
- Age assessment
- Risk score

## Scoring

| Age | Score | Severity |
|-----|-------|----------|
| Current (0-3 months) | 100 | LOW |
| Slightly outdated (3-6 months) | 70 | MEDIUM |
| Outdated (6-12 months) | 40 | HIGH |
| Very outdated (12+ months) | 10 | CRITICAL |

## Severity Model

| Age | Severity |
|-----|----------|
| Current (0-3 months) | LOW |
| Slightly outdated (3-6 months) | MEDIUM |
| Outdated (6-12 months) | HIGH |
| Very outdated (12+ months) | CRITICAL |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Device-specific expected | Check device EOL status |
| Vendor delay | Check vendor patch cycle |
| Development build | Check build type |
