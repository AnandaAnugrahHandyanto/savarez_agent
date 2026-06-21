# Recovery-Only Diagnostics Reference

## Purpose

Diagnose why device boots to recovery only.

## Inputs

- Recovery log
- Boot partition status
- System partition integrity

## Detection Logic

### Recovery Reason

```bash
getprop ro.bootmode 2>/dev/null
```

### Recovery Log

```bash
cat /tmp/recovery.log 2>/dev/null | tail -50
```

### System Mount Failure

```bash
dmesg 2>/dev/null | grep "mount.*system.*fail"
```

### Signature Verification

```bash
grep "signature\|verification" recovery.log 2>/dev/null
```

## Output Format

- Recovery trigger reason
- System integrity status
- Mount failures
- Recommended fix

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | Clear trigger reason identified |
| PROBABLE | Mount failure detected |
| POSSIBLE | Recovery mode active, cause unclear |
| UNKNOWN | Insufficient recovery log |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| User-initiated | Check trigger |
| OTA failures | Check update log |
| Corrupted recovery | Verify recovery |
