# Commit Message Generator Reference

## Purpose

Generate proper commit messages for fixes.

## Inputs

- Fix description
- Affected files
- Root cause

## Detection Logic

### Analyze Changed Files

```bash
git diff --name-only | head -10
```

### Analyze Change Type

```bash
git diff --stat | tail -1
```

### Determine Scope

```bash
# Extract component from path
git diff --name-only | head -1 | cut -d/ -f1-2
```

## Output Format

Conventional commit format:

```
<type>(<scope>): <description>

<body>

<footer>
```

### Types

| Type | Description |
|------|-------------|
| fix | Bug fix |
| feat | New feature |
| refactor | Code refactor |
| docs | Documentation |
| test | Tests |
| chore | Maintenance |

### Examples

```
fix(camera): resolve null pointer in camera HAL

Root cause: Camera HAL service crashes when accessing
uninitialized camera device pointer.

Fix: Initialize camera device pointer to NULL and add
null check before accessing.

Affected: hardware/qcom/camera/
```

```
fix(sepolicy): add missing camera_server permissions

Root cause: SELinux denial when camera_server accesses
camera device nodes.

Fix: Add minimal allow rules for camera operation.

Affected: device/xiaomi/onyx/sepolicy/
```

## Risk Level Guidance

| Change Type | Risk |
|-------------|------|
| Documentation | LOW |
| Config change | LOW |
| Code fix | MEDIUM |
| API change | HIGH |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Wrong type | Check change nature |
| Missing scope | Check file path |
| Vague description | Include root cause |
