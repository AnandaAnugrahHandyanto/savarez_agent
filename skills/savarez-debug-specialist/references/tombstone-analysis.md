# Tombstone Analysis Reference

## Purpose

Analyze Android native crash tombstones.

## Inputs

- Tombstone file from /data/tombstones/
- Crash dump

## Detection Logic

### Signal Info

```bash
grep "signal\|fault addr" tombstone.txt 2>/dev/null | head -5
```

### Backtrace

```bash
grep -A20 "backtrace:" tombstone.txt 2>/dev/null
```

### Registers

```bash
grep -A15 "registers:" tombstone.txt 2>/dev/null
```

### Memory Map

```bash
grep -A10 "memory map:" tombstone.txt 2>/dev/null
```

## Output Format

- Crash signal (SIGSEGV, SIGABRT, etc.)
- Fault address
- Faulting library/function
- Register state

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | Signal + library + function identified |
| PROBABLE | Signal + library identified |
| POSSIBLE | Signal identified, library unclear |
| UNKNOWN | Incomplete tombstone |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Stripped binaries | Check for symbols |
| ASLR offsets | Normalize addresses |
| Multiple tombstones | Analyze newest |
