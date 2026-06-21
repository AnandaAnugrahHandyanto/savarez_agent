# Signing & Verification Audit Reference

## Purpose

Validate image signing and verification mechanisms.

## Inputs

- Boot image
- System image
- Vendor image
- Signing keys

## Detection Logic

### AVB Status

```bash
grep -i "avb" boot.img 2>/dev/null
```

### dm-verity Status

```bash
grep -i "dm-verity\|verity" fstab
```

### Signature Files

```bash
find . -name "*.sig" -o -name "*.Sign" 2>/dev/null
```

### Boot Image Signing

```bash
file boot.img | grep -i "signed"
```

## Output Format

- AVB status
- dm-verity status
- Signature verification
- Signing risk score

## Scoring

| Factor | Points |
|--------|--------|
| AVB enabled | +30 |
| dm-verity enabled | +30 |
| Signatures verified | +25 |
| No unsigned images | +15 |

## Severity Model

| Finding | Severity |
|---------|----------|
| AVB disabled | CRITICAL |
| dm-verity disabled | HIGH |
| Missing signatures | HIGH |
| Weak signing key | MEDIUM |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Debug builds | Check build type |
| Development mode | Check ro.debuggable |
| Expected unsigned | Check image type |
