# Kernel Config Patch Recommendation Reference

## Purpose

Recommend kernel config fixes.

## Inputs

- Kernel config errors
- Build failures
- Missing features

## Detection Logic

### Missing Config

```bash
grep -i "config.*missing\|\.config.*error" build.log
```

### Feature Disabled

```bash
grep -i "feature.*disabled\|not enabled" build.log
```

### Config Mismatch

```bash
diff defconfig .config | grep -i "config"
```

## Output Format

- Root cause: Missing/incorrect kernel config
- Recommended change: Enable config option
- Affected files: arch/arm64/configs/
- Example diff:
```diff
+CONFIG_USB_CONFIGFS=y
+CONFIG_USB_CONFIGFS_F_HID=y
```
- Risk level: LOW

## Risk Level Guidance

| Config Type | Risk |
|-------------|------|
| Enable feature | LOW |
| Disable feature | MEDIUM |
| Module change | MEDIUM |
| Subsystem change | HIGH |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Dependency | Check depends |
| Hardware required | Check hardware |
| Conflict | Check conflicts |
