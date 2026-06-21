# Fastboot-Only Diagnostics Reference

## Purpose

Diagnose why device is stuck in fastboot mode.

## Inputs

- Fastboot variables
- Boot partition status
- Device state

## Detection Logic

### Device State

```bash
fastboot getvar is-unlocked 2>/dev/null
fastboot getvar is-userspace 2>/dev/null
```

### Boot Partition

```bash
fastboot getvar has-slot:boot 2>/dev/null
```

### Last Boot Reason

```bash
fastboot getvar last-boot 2>/dev/null
```

## Output Format

- Lock state
- Boot partition status
- Boot failure reason
- Recommended fix

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | Clear boot failure reason |
| PROBABLE | Lock state or partition issue |
| POSSIBLE | Fastboot active, cause unclear |
| UNKNOWN | Insufficient fastboot data |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| User-initiated | Check trigger |
| Failed flash | Check flash log |
| Corrupted boot | Verify boot image |
