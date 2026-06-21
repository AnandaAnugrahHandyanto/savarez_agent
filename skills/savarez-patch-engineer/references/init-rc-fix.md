# Init.rc Fix Analysis Reference

## Purpose

Analyze and fix init.rc issues.

## Inputs

- init.rc files
- Boot log
- Service definitions

## Detection Logic

### Syntax Errors

```bash
grep -n "error\|fail" init.log | grep "init"
```

### Service Failures

```bash
grep "Service.*fail\|Service.*restart" logcat.txt
```

### Permission Issues

```bash
grep "permission.*denied\|cannot.*open" init.log
```

## Output Format

- Root cause: Init script syntax / service failure
- Recommended change: Fix syntax / service config
- Affected files: device/*/init.*.rc
- Example diff:
```diff
- service vendor.foo /system/bin/foo
+ service vendor.foo /system/bin/foo
+     class main
+     user system
+     group system
```
- Risk level: MEDIUM

## Risk Level Guidance

| Issue Type | Risk |
|------------|------|
| Syntax fix | LOW |
| Service class | MEDIUM |
| Permission change | MEDIUM |
| Service dependency | HIGH |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Service ordering | Check dependencies |
| Permission change | Check SELinux |
| Class assignment | Check boot sequence |
