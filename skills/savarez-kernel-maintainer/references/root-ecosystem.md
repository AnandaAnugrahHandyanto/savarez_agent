# Root Ecosystem Audit Reference

## Purpose

Detect KernelSU, KernelSU Next, SUSFS, and root frameworks.

## Detection Matrix

| Framework | Detection |
|-----------|-----------|
| KernelSU Next + SUSFS | KERNELSU ≥2 + hooks ≥1 + KSU_NEXT + SUSFS ≥2 |
| KernelSU + SUSFS | KERNELSU ≥2 + hooks ≥1 + SUSFS ≥2 |
| KernelSU Next | KERNELSU ≥2 + hooks ≥1 + KSU_NEXT |
| KernelSU | KERNELSU ≥2 + hooks ≥1 |
| KernelSU (partial) | KERNELSU ≥1 only |
| None | No indicators |

## Scoring

| Framework | Score |
|-----------|-------|
| KernelSU Next + SUSFS | 10 |
| KernelSU + SUSFS | 9 |
| KernelSU Next | 8 |
| KernelSU | 7 |
| KernelSU (partial) | 4 |
| None | 0 |

## False-Positive Prevention

| Risk | Mitigation |
|------|------------|
| Generic "ksu" match | Require uppercase KERNELSU |
| False SUSFS | Require ≥2 references |
| False Next | Require KSU_NEXT indicators |

## Detection Logic

```bash
# CORRECT: Require uppercase + hooks
KSU_UPPER=$(grep -c "KERNELSU" kernel/ 2>/dev/null || echo "0")
KSU_HOOKS=$(grep -c "ksu_hook\|allow_su\|ksu_handle" kernel/ 2>/dev/null || echo "0")

if [ "$KSU_UPPER" -gt 2 ] && [ "$KSU_HOOKS" -gt 0 ]; then
    FRAMEWORK="KernelSU"
fi

# WRONG: Generic string match
grep -r "ksu" kernel/  # Too broad, false positives
```

## Example Output

```
=== Kernel Root Ecosystem Audit ===

Framework: KernelSU + SUSFS
KernelSU: 23 refs, 8 hooks
SUSFS: 12 refs
Root Ecosystem: 9/10
```
