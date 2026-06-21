# VINTF Compatibility Fix Reference

## Purpose

Fix VINTF manifest and compatibility issues.

## Inputs

- VINTF error log
- manifest.xml
- compatibility_matrix.xml

## Detection Logic

### Missing HAL

```bash
grep -i "vintf.*missing\|hal.*not found" logcat.txt
```

### Version Mismatch

```bash
diff <(grep "version" manifest.xml) <(grep "version" compatibility_matrix.xml)
```

### Interface Error

```bash
grep -i "interface.*error\|version.*mismatch" logcat.txt
```

## Output Format

- Root cause: Missing/incorrect HAL version
- Recommended change: Add/update HAL entry
- Affected files: device/*/manifest.xml
- Example diff:
```diff
+<hal format="aidl">
+    <name>android.hardware.example</name>
+    <version>1</version>
+    <interface>
+        <name>IDevice</name>
+        <instance>default</instance>
+    </interface>
+</hal>
```
- Risk level: MEDIUM

## Risk Level Guidance

| Issue Type | Risk |
|------------|------|
| Add optional HAL | LOW |
| Add required HAL | MEDIUM |
| Version bump | MEDIUM |
| Interface change | HIGH |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Optional HALs | Check if required |
| Legacy HALs | Check version |
| AIDL vs HIDL | Check interface type |
