# Permission Overuse Detection Reference

## Purpose

Detect applications and services with excessive permissions.

## Inputs

- AndroidManifest.xml files
- Permission declarations
- App permissions

## Detection Logic

### Dangerous Permissions

```bash
grep -r "android.permission" AndroidManifest.xml | \
    grep -E "READ_|WRITE_|ACCESS_" | wc -l
```

### SignatureOrSystem Permissions

```bash
grep -r "signatureOrSystem" AndroidManifest.xml | wc -l
```

### Custom Permissions

```bash
grep -r "android:protectionLevel" AndroidManifest.xml
```

## Output Format

- Dangerous permission count
- SignatureOrSystem count
- Custom permission analysis
- Permission risk score

## Scoring

| Factor | Points |
|--------|--------|
| Dangerous permissions < 10 | +30 |
| No signatureOrSystem abuse | +30 |
| Protection levels set | +20 |
| No custom permissions | +20 |

## Severity Model

| Finding | Severity |
|---------|----------|
| Excessive dangerous permissions | HIGH |
| SignatureOrSystem abuse | MEDIUM |
| Custom permission weak | MEDIUM |
| Missing protectionLevel | LOW |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| System app permissions | Check if system app |
| Expected permissions | Check app function |
| Legacy permissions | Check target SDK |
