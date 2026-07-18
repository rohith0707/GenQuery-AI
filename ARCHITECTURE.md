# GenQuery AI - Architecture Deep Dive

## System Design Overview

Multi-layer LLM system converting natural language SQL to deterministic execution:

[ASCII DIAGRAM showing:]
User Intent → Intent Parser (Claude) → Schema Retrieval → SQL Generation → Validation → Execution

## Why This Architecture

**Problem:** Off-the-shelf LLM SQL generation hallucinates, fails validation, causes compliance issues.

**Solution:** 
- Intent parsing layer catches ambiguous queries pre-generation
- Schema-aware prompting (system message includes target schema)
- Structured output validation ensures execution readiness
- Read-only gates prevent data mutation

## Trade-Offs

- Added latency: 300ms intent parsing + 400ms SQL gen = 700ms total (worth it for accuracy)
- Complexity: Multi-stage pipeline vs single LLM call
- But: 98% accuracy vs 65% accuracy with naive approach

## Evaluation Framework

500+ test cases covering:
- Simple SELECT queries
- Complex JOINs
- Aggregations with GROUP BY
- Edge cases (NULL handling, type mismatches)
- Schema mismatches

See `evaluation/test_cases.py` for full suite.

## Results

- Accuracy: 98% on validation set
- Latency: p95 < 2 seconds
- Throughput: 100K+ queries/day
- Cost per query: $0.003 (GPT-4)

## Production Patterns

### 1. Cost Optimization
GPT-4 → Claude (cheaper for SQL) = 30% cost reduction

### 2. Fallback Strategy
If SQL generation fails:
1. Retry with different prompt
2. Fallback to simpler schema subset
3. If still fails, escalate to human

### 3. Observability
Every query logged with:
- Intent parsing confidence
- SQL generation latency
- Validation status
- Actual execution time
- Cost per query

Used LangSmith for full observability.

## Scaling Considerations

### From 10K → 100K daily queries

What broke:
- Database connection pooling (solved: added connection limits)
- LLM rate limits (solved: queued long-running queries)
- Cache miss rates (solved: cached schema + intent patterns)

What we optimized:
- Batch schema retrieval (vs individual queries)
- Prompt caching for repeated schema patterns
- Token count reduction through selective context

## Future Work

1. Fine-tuned models on domain-specific SQL
2. Graph-based schema understanding (vs text-based)
3. Real-time cost prediction per query
4. Multi-LLM ranking (use Claude for complex, GPT-4o for simple)
