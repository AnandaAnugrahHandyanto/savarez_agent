# Bring-Up Diagnostics Reference

## Overview

Analyzes common build and boot failures for Android ROM.

---

## Diagnostic Categories

| Category | Patterns | Severity |
|----------|----------|----------|
| Build failures | Missing deps, kernel errors | HIGH |
| Boot failures | Kernel panic, init crash | CRITICAL |
| Logcat patterns | ANR, crash, permission | MEDIUM |
| Kernel issues | Panic, oops, driver | CRITICAL |

---

## Build Failure Patterns

### Missing Makefile Rule

```bash
grep -r "No rule to make target" . 2>/dev/null
```

**Fix:** Check Android.mk for typos.

### Permission Error

```bash
grep -r "Permission denied" . 2>/dev/null
```

**Fix:** Check file permissions.

### SELinux Denial

```bash
grep -r "SELinux: denied" . 2>/dev/null
```

**Fix:** Add policy rule.

---

## Boot Failure Patterns

### Kernel Panic

```bash
grep -r "kernel panic" . 2>/dev/null
```

**Fix:** Check kernel config and drivers.

### Init Service Loop

```bash
grep -r "init: Service.*restarting" . 2>/dev/null
```

**Fix:** Check service dependencies.

### Zygote Crash

```bash
grep -r "Zygote.*died" . 2>/dev/null
```

**Fix:** Check system_server and dependencies.

---

## Common Fixes

| Issue | Fix |
|-------|-----|
| Kernel panic | Verify defconfig, check drivers |
| SELinux denial | Add allow rule to device.te |
| Init loop | Check service dependencies |
| Zygote crash | Verify system_server |
