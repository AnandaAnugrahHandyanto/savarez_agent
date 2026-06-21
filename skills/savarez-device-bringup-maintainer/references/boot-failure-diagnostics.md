# Boot Failure Diagnostics Reference

## Purpose

Detect common boot failures. Informational only — not scored.

## Checks

| Check | Weight | Description |
|-------|--------|-------------|
| Bootloop | 14.3% | Boot loop pattern |
| Fastboot-only | 14.3% | Stuck in fastboot |
| Recovery-only | 14.3% | Recovery boot only |
| Black screen | 14.3% | Display failure |
| system_server crash | 14.3% | System crash |
| SELinux denial storm | 14.3% | SELinux denials |
| Kernel panic | 14.3% | Kernel crash |

## Detection Methods

### Bootloop

```bash
dmesg 2>/dev/null | grep -q "boot completed" | grep -v "1" && echo "[!] Bootloop detected"
```

### Fastboot-only

```bash
fastboot getvar product 2>/dev/null | grep -q . && echo "[!] Fastboot-only mode"
```

### Recovery-only

```bash
getprop ro.bootmode 2>/dev/null | grep -q "recovery" && echo "[!] Recovery-only mode"
```

### Black Screen

```bash
dmesg 2>/dev/null | grep -qE "dsi|panel|drm" | grep -q "error\|fail" && echo "[!] Display failure"
```

### system_server Crash

```bash
logcat 2>/dev/null | grep -q "system_server.*died\|system_server.*crash" && echo "[!] system_server crash"
```

### SELinux Denial Storm

```bash
dmesg 2>/dev/null | grep -c "avc:.*denied" | awk '{if($1>100) print}' | grep -q . && echo "[!] SELinux denial storm"
```

### Kernel Panic

```bash
dmesg 2>/dev/null | grep -q "panic\|oops\|BUG:" && echo "[!] Kernel panic"
```

## Score

Not scored (informational only)

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Normal boot messages | Filter critical errors |
| Vendor-specific logs | Check common patterns |
| Transient failures | Check repeated occurrences |
| Device required | Diagnostic only |
