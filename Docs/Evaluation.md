# Evaluation Framework

## The Problem

LLM SQL generation is unreliable. How do you measure reliability at scale?

## Our Solution: 500-Test Case Suite

### Categories

1. **Basic Queries (50 tests)** - Simple SELECT, WHERE
2. **Joins (75 tests)** - INNER, LEFT, multiple joins
3. **Aggregations (50 tests)** - GROUP BY, HAVING
4. **Edge Cases (100 tests)** - NULL handling, type mismatches
5. **Schema Mismatches (75 tests)** - Non-existent columns (should fail gracefully)
6. **Complex Queries (150 tests)** - Real-world analyst queries

### Metrics

- **Accuracy:** Generated SQL matches expected output
- **Latency:** p50, p95, p99 execution time
- **Cost:** Tokens used per query
- **Failure modes:** How does it fail when it fails?

### Current Performance

- Overall accuracy: 98%
- By category: See `evaluation/results.csv`
- Latency p95: 1.8 seconds
- Cost per query: $0.003 average

### Continuous Evaluation

Every new model version runs full 500-test suite before production deployment.

### Open Questions

- Can fine-tuning push from 98% → 99%?
- Do different schema formats change accuracy?
- Cost-accuracy trade-offs: Claude vs GPT-4?

See `evaluation/notebooks/` for analysis.
