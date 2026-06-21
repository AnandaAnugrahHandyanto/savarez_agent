---
name: savarez-testing-specialist
description: "Android testing: CTS, VTS, STS, functional, regression, performance, stability, boot, hardware validation, test reporting."
---

# Savarez Testing Specialist

Execute, analyze, and report on Android ROM and kernel testing.

## Purpose

Analyze test results and generate validation reports. This skill does not execute tests — it analyzes test outputs and provides pass/fail assessments.

## Skill Type

- **Testing-based** (analysis only)
- **No test execution**
- **No runtime dependencies**
- **Documentation-driven**

## When to Use

| Scenario | Use This Skill |
|----------|----------------|
| CTS result analysis | ✅ |
| VTS result analysis | ✅ |
| STS result analysis | ✅ |
| Functional test analysis | ✅ |
| Regression detection | ✅ |
| Performance benchmarking | ✅ |
| Stability analysis | ✅ |
| Boot validation | ✅ |
| Hardware validation | ✅ |
| Test report generation | ✅ |
| Root cause analysis | Use savarez-debug-specialist |
| Security posture audit | Use savarez-security-auditor |
| Fix generation | Use savarez-patch-engineer |

## Capabilities

### 10 Capabilities

| # | Capability | Weight | Purpose |
|---|------------|--------|---------|
| 1 | CTS Compatibility Test | 20% | Android compatibility |
| 2 | VTS Vendor Test | 15% | Vendor HAL compliance |
| 3 | STS Security Test | 15% | Security patch verification |
| 4 | Functional Test Suite | 15% | Core functionality |
| 5 | Regression Test Manager | 10% | Change impact testing |
| 6 | Performance Benchmark | 10% | Speed/memory/battery |
| 7 | Stability Test Runner | 5% | Stress/endurance |
| 8 | Boot Test Validator | 5% | Boot success/failure |
| 9 | Hardware Component Test | 5% | Component validation |
| 10 | Test Report Generator | — | Results documentation |

---

## Analysis-Based Design

This skill analyzes test results — it does NOT execute tests.

| Aspect | Design |
|--------|--------|
| Input | Test result files (XML/JSON/logs) |
| Processing | Parse, count, calculate |
| Output | Pass/fail reports |
| Execution | Not performed |

---

## Separation Statements

### STS Test vs Security Auditor

| Aspect | STS Test (This Skill) | Security Auditor |
|--------|----------------------|------------------|
| Focus | STS test suite results | Security posture audit |
| Input | Test XML results | Policy, permissions, configs |
| Output | Test pass rate | Security score |
| Workflow | Test execution phase | Audit phase |

**STS provides test pass rates. Security Auditor provides security scores.**

### Performance Benchmark vs Performance Profiler (Future)

| Aspect | Performance Benchmark (This Skill) | Performance Profiler (Future) |
|--------|-----------------------------------|------------------------------|
| Focus | Benchmark pass/fail, score comparison | Deep profiling, optimization |
| Input | Benchmark results | Runtime metrics |
| Output | Score comparison, variance | Bottleneck analysis, recommendations |
| Depth | Surface-level metrics | Deep analysis |

**Performance Benchmark provides score comparison. Performance Profiler provides optimization recommendations.**

---

## Scoring Model

```
Test Score = (
    CTS Score * 0.20 +
    VTS Score * 0.15 +
    STS Score * 0.15 +
    Functional Score * 0.15 +
    Regression Score * 0.10 +
    Performance Score * 0.10 +
    Stability Score * 0.05 +
    Boot Score * 0.05 +
    Hardware Score * 0.05
)
```

## Test Categories

| Score | Category |
|-------|----------|
| 95-100 | EXCELLENT |
| 85-94 | GOOD |
| 70-84 | ACCEPTABLE |
| 50-69 | POOR |
| 0-49 | FAILING |

---

## Output Format

Every capability produces:

```
=== [Capability Name] ===
Total tests: [count]
Pass: [count]
Fail: [count]
Pass rate: [percentage]%
Status: [PASS/WARNING/FAIL]
```

Final report:

```
=== Test Report ===
Device: [name]
Build: [version]

=== Test Results ===
CTS: [score]% ([status])
VTS: [score]% ([status])
STS: [score]% ([status])
...

=== Overall Score: [score]/100 ===
Category: [EXCELLENT/GOOD/ACCEPTABLE/POOR/FAILING]

=== Status: [READY/NOT READY] ===
```

---

## Reference Files

| File | Purpose |
|------|---------|
| cts-compatibility.md | CTS test analysis |
| vts-vendor.md | VTS test analysis |
| sts-security.md | STS test analysis |
| functional-test.md | Functional test analysis |
| regression-test.md | Regression detection |
| performance-benchmark.md | Benchmark analysis |
| stability-test.md | Stability analysis |
| boot-test.md | Boot validation |
| hardware-test.md | Hardware validation |
| test-report.md | Report generation |

---

## Example Output

```
=== Test Report ===

Device: Poco F7 (onyx)
Build: lineage-onyx-userdebug

=== Test Results ===
CTS: 99.0% (PASS)
VTS: 96.5% (PASS)
STS: 100% (PASS)
Functional: 97.5% (PASS)
Regression: 0 (PASS)
Performance: +2% (PASS)
Stability: 0 crashes (PASS)
Boot: 100% (PASS)
Hardware: 98.0% (PASS)

=== Overall Score: 97.8/100 ===
Category: EXCELLENT

=== Status: READY FOR RELEASE ===
```

---

## Notes

- All analysis is based on test result files
- No test execution is performed
- Pass rates are calculated from provided data
- Regression is detected by comparing with previous results
- Hardware validation covers major component categories
