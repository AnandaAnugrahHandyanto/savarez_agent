# Kernel Panic Analysis Reference

## Purpose

Analyze kernel panic logs for root cause.

## Inputs

- Panic log from /proc/last_kmsg or pstore
- Ramdump analysis

## Detection Logic

### Panic Signature

```bash
grep -A20 "Kernel panic" panic.log 2>/dev/null
```

### Call Trace

```bash
grep -A30 "Call trace:" panic.log 2>/dev/null
```

### Faulting Address

```bash
grep "PC is at\|pc :" panic.log 2>/dev/null
```

### Module Info

```bash
grep "Modules linked in:" panic.log 2>/dev/null
```

## Output Format

- Panic type (NULL pointer, oops, hung task, etc.)
- Faulting function/module
- Call trace summary
- Recommended fix

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | Panic type + faulting function identified |
| PROBABLE | Panic type identified, function unclear |
| POSSIBLE | Panic detected, root cause unclear |
| UNKNOWN | Incomplete panic log |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Multiple panics | Analyze most recent |
| Incomplete logs | Request full log |
| Symbolic vs raw addresses | Use addr2line if available |
