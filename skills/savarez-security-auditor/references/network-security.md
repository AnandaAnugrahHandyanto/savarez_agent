# Network Security Audit Reference

## Purpose

Validate network security configurations.

## Inputs

- Network permissions
- SSL/TLS configurations
- Certificate stores

## Detection Logic

### Network Permissions

```bash
grep -r "android.permission.INTERNET" AndroidManifest.xml | wc -l
```

### Cleartext Traffic

```bash
grep -r "usesCleartextTraffic" AndroidManifest.xml
```

### Network Security Config

```bash
find . -name "network_security_config.xml" 2>/dev/null
```

### Certificate Pinning

```bash
grep -r "pin-set\|certificate" network_security_config.xml 2>/dev/null
```

## Output Format

- Network permission count
- Cleartext traffic status
- SSL/TLS configuration
- Network security risk score

## Scoring

| Factor | Points |
|--------|--------|
| No cleartext traffic | +30 |
| SSL/TLS configured | +30 |
| Certificate pinning | +20 |
| Network security config present | +20 |

## Severity Model

| Finding | Severity |
|---------|----------|
| Cleartext allowed | HIGH |
| Weak SSL/TLS | HIGH |
| Missing cert pinning | MEDIUM |
| Excessive network permissions | MEDIUM |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Expected cleartext | Check app purpose |
| Debug builds | Check build type |
| Legacy compatibility | Check target SDK |
