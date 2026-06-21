# Performance Benchmark Reference

## Purpose

Measure and validate performance metrics.

## Inputs

- Benchmark results (AnTuTu, Geekbench, etc.)
- Baseline metrics
- Device specs

## SCOPE BOUNDARIES

**Performance Benchmark vs Performance Profiler (Future):**

| Aspect | Performance Benchmark (This Skill) | Performance Profiler (Future) |
|--------|-----------------------------------|------------------------------|
| Focus | Benchmark pass/fail, score comparison | Deep profiling, optimization |
| Input | Benchmark results | Runtime metrics |
| Output | Score comparison, variance | Bottleneck analysis, recommendations |
| Depth | Surface-level metrics | Deep analysis |

**Performance Benchmark provides score comparison. Performance Profiler provides optimization recommendations.**

## Detection Logic

### Parse Benchmark Scores

```bash
# Extract scores
grep -i "score" benchmark_results.txt | head -5

# Get total score
CURRENT_SCORE=$(grep "total" benchmark_results.txt | awk '{print $2}')
```

### Compare with Baseline

```bash
# Set baseline
BASELINE_SCORE=100000

# Calculate variance
VARIANCE=$(( (CURRENT_SCORE - BASELINE_SCORE) * 100 / BASELINE_SCORE ))
```

## Output Format

- Benchmark scores
- Baseline comparison
- Variance percentage
- Performance status

## Validation Criteria

| Metric | Threshold | Status |
|--------|-----------|--------|
| Variance | ±5% | PASS |
| Variance | ±10% | WARNING |
| Variance | > ±10% | FAIL |

## Scoring

| Variance | Score |
|----------|-------|
| ±0-5% | 100 |
| ±5-10% | 80 |
| ±10-15% | 60 |
| > ±15% | 40 |

## False-Positive Mitigation

| Risk | Mitigation |
|------|------------|
| Background processes | Check system load |
| Thermal throttling | Check temperature |
| Test variability | Run multiple iterations |
