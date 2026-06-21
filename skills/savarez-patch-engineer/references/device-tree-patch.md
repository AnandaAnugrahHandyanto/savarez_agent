# Device Tree Patch Analysis Reference

## Purpose

Analyze device tree for issues.

## Inputs

- DTS/DTSI files
- Build errors
- Boot log

## Detection Logic

### DTS Errors

```bash
grep -i "dtc.*error\|dts.*error" build.log
```

### Missing Nodes

```bash
grep -i "node.*missing\|property.*missing" build.log
```

### Phandle Errors

```bash
grep -i "phandle.*error\|reference.*error" build.log
```

## Output Format

- Root cause: Device tree syntax / missing node
- Recommended change: Fix DTS syntax / add node
- Affected files: arch/arm64/boot/dts/
- Example diff:
```diff
+    camera@1 {
+        compatible = "vendor,camera";
+        reg = <0x1>;
+    };
```
- Risk level: MEDIUM

## Risk Level Guidance

| Issue Type | Risk |
|------------|------|
| Syntax fix | LOW |
| Add property | LOW |
| Add node | MEDIUM |
| Modify existing | HIGH |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Phandle reference | Check target exists |
| Unit address | Check reg property |
| Compatible string | Check driver exists |
