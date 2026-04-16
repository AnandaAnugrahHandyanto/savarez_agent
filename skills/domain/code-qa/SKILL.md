---
name: code-qa
description: Code quality assurance — identify and fix bugs, parsing edge cases, code cleanup, security vulnerabilities across 5 difficulty levels using Prime Intellect evaluation.
version: 1.0.0
author: tonyteo
license: MIT
metadata:
  hermes:
    tags: [Code, QA, Debugging, Python, Security, Parsing, Bug-Fixing]
    related_skills: [test-driven-development, systematic-debugging, requesting-code-review]
---

# Code QA — Correct with Minor QA

Progressive code quality assurance skill for identifying and fixing bugs, parsing edge cases, and code quality issues.

## When to Use

- User shares buggy code and asks for fixes
- Code review requests
- Finding edge cases in parsing logic
- Security vulnerability detection (SQL injection, eval, XSS)
- Code cleanup and PEP 8 compliance

## Levels

| Level | Focus | Complexity |
|-------|-------|------------|
| 1 | Basic Cleanup | Unused imports, dead code, naming, magic numbers |
| 2 | Parsing Edge Cases | Off-by-one, null/None, boundary conditions |
| 3 | Multi-Turn Review | LRU cache, pipeline, concurrency, serialization |
| 4 | Tool-Use Debugging | Algorithm bugs, parsers, validation, state machines |
| 5 | Specialist Analysis | Async bugs, SQL injection, template XSS |

## Workflow

### Step 1: Analyze

Read the code carefully. Check for:

- **Syntax errors** — will it even parse?
- **Off-by-one errors** — `range(len(x))` vs `range(1, len(x))`
- **Null/None handling** — `if x:` vs `if x is not None:`
- **Boundary conditions** — empty lists, single elements, negative numbers
- **Resource leaks** — unclosed files, sessions, connections
- **Security** — `eval()`, SQL string concatenation, unsanitized input
- **Performance** — O(n²) when O(n) is possible, missing memoization

### Step 2: Fix

Provide the corrected code in a ```python code block. Keep the fix minimal — don't rewrite the entire code unless necessary.

### Step 3: Explain

Briefly explain each issue found:
1. What was wrong
2. Why it's a problem
3. How the fix addresses it

## Common Patterns

### Unused imports & dead code
```python
# BEFORE
import os, sys, json, re, math  # only math is used
def unused_func(): pass

# AFTER
import math
```

### Off-by-one in slicing
```python
# BEFORE — returns one character short
def get_substring(s, start, length):
    return s[start:start + length - 1]  # BUG: -1

# AFTER
def get_substring(s, start, length):
    return s[start:start + length]
```

### Null/None handling
```python
# BEFORE — crashes on empty list
def safe_average(numbers):
    return sum(numbers) / len(numbers)  # ZeroDivisionError

# AFTER
def safe_average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)
```

### Binary search boundary
```python
# BEFORE — infinite loop when target is last element
while low < high:  # should be <=

# AFTER
while low <= high:
    mid = (low + high) // 2
```

### SQL injection
```python
# BEFORE — vulnerable
query = f"SELECT * FROM users WHERE name = '{name}'"

# AFTER — parameterized
query = "SELECT * FROM users WHERE name = ?"
cursor.execute(query, (name,))
```

### Template eval vulnerability
```python
# BEFORE — arbitrary code execution
if eval(condition, {"__builtins__": {}}, context):

# AFTER — safe lookup
if context.get(condition.strip()):
```

## Prime Intellect Evaluation

Run evaluations on the Prime Intellect Environments Hub:

```bash
# Install
prime env install tonyteo/code-qa

# Evaluate all levels
prime eval run tonyteo/code-qa -m <model>

# Evaluate up to level N
prime eval run tonyteo/code-qa -m <model> --env-args '{"level": 3}'
```

## Scoring (AST-based)

The environment uses static analysis (no subprocess execution):
- **Unused imports** (30%) — detects imported modules never referenced
- **Dead code** (30%) — functions defined but never called
- **Naming** (20%) — PEP 8 compliance (snake_case functions, etc.)
- **Magic numbers** (20%) — hardcoded values that should be constants

Scores: 0.96+ = clean fix, 0.66 = partial fix, 0.49 = no fix, 0.1 = syntax error
