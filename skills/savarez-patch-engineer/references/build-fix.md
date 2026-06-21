# Build Fix Generator Reference

## Purpose

Generate fixes for build failures.

## Inputs

- Build error log
- Error location (file, line)
- Error type

## Detection Logic

### Missing Header Fix

```bash
if grep -q "No such file or directory" build.log; then
    HEADER=$(grep "No such file or directory" build.log | head -1 | awk '{print $NF}')
    echo "Add #include <$HEADER> or add to include path"
fi
```

### Undefined Reference Fix

```bash
if grep -q "undefined reference" build.log; then
    SYMBOL=$(grep "undefined reference" build.log | head -1 | grep -o '"[^"]*"' | tr -d '"')
    echo "Add library containing $SYMBOL to LOCAL_SHARED_LIBRARIES"
fi
```

### Syntax Error Fix

```bash
if grep -q "syntax error" build.log; then
    LINE=$(grep "syntax error" build.log | head -1 | grep -o "[0-9]*")
    echo "Check line $LINE for syntax"
fi
```

## Output Format

- Root cause
- Recommended change
- Affected files
- Example diff
- Risk level: LOW

## Risk Level Guidance

| Error Type | Risk |
|------------|------|
| Missing header | LOW |
| Undefined reference | LOW |
| Syntax error | LOW |
| Linker error | MEDIUM |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Cascading errors | Focus on first error |
| Missing context | Request full build log |
| Multiple fixes | Provide options |
