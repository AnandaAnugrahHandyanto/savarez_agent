# Dmesg Analysis Reference

## Purpose

Analyze kernel ring buffer for hardware and driver issues.

## Inputs

- dmesg output or /proc/kmsg
- Filter: time range, severity

## Detection Logic

### Kernel Errors

```bash
dmesg 2>/dev/null | grep -i "error\|fail\|panic\|oops" | head -20
```

### Hardware Errors

```bash
dmesg 2>/dev/null | grep -i "hardware\|iommu\|smmu\|ecc" | head -10
```

### Driver Errors

```bash
dmesg 2>/dev/null | grep -i "driver\|probe\|init" | grep -i "fail\|error" | head -10
```

### OOM Events

```bash
dmesg 2>/dev/null | grep -i "out of memory\|oom" | head -5
```

## Output Format

- Hardware error summary
- Driver failure list
- OOM events
- Temperature warnings

## Confidence Assessment

| Level | Criteria |
|-------|----------|
| CONFIRMED | Clear error with hardware reference |
| PROBABLE | Driver failure with module info |
| POSSIBLE | Generic error pattern |
| UNKNOWN | Insufficient log data |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Normal boot messages | Filter by severity |
| Informational messages | Ignore info level |
| Deprecated warnings | Check relevance |
