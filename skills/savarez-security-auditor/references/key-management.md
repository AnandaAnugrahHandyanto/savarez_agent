# Key Management Audit Reference

## Purpose

Validate cryptographic key management practices.

## Inputs

- Key directory structure
- Key permissions
- Key type (test/production)

## Detection Logic

### Key Locations

```bash
find . -name "*.pem" -o -name "*.key" -o -name "*.pk8" 2>/dev/null
```

### Key Permissions

```bash
ls -la *.key *.pem 2>/dev/null
```

### Test Key Detection

```bash
# Check for test/default key indicators
grep -r "testkey\|platform\.pk8\|shared\.pk8\|media\.pk8" . 2>/dev/null
```

### Key Rotation

```bash
grep -i "key.rotation\|key.version" build.prop
```

## Output Format

- Key inventory
- Permission status
- Key type (test/production)
- Rotation status
- Key management risk score

## Scoring

| Factor | Points |
|--------|--------|
| Keys not exposed | +25 |
| Proper permissions | +25 |
| Production keys | +25 |
| Key rotation enabled | +25 |

## Severity Model

| Finding | Severity |
|---------|----------|
| Exposed private keys | CRITICAL |
| Test keys in production | HIGH |
| Weak key permissions | HIGH |
| No key rotation | MEDIUM |
| Default keys | MEDIUM |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Test keys expected | Check build type |
| Development keys | Check build type |
| Expected defaults | Check release status |
