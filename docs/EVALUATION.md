# Evaluation

GenQuery-AI should be evaluated as a system, not only by whether an individual generated SQL query looks plausible.

## Evaluation dimensions

| Dimension | What to measure |
|---|---|
| SQL validity | Does generated SQL parse and execute safely? |
| Task correctness | Does the query answer the intended analytical question? |
| Schema grounding | Does generation use the relevant tables and columns? |
| Safety | Are non-read operations and multi-statement attempts rejected? |
| Robustness | Does the system recover from provider/tool/query failures? |
| Latency | End-to-end and model-generation latency |
| Cost | Tokens/provider cost per request |

## Regression dataset

Add representative natural-language questions covering:

1. simple aggregation
2. joins
3. date filtering
4. grouping and ranking
5. nested queries / CTEs
6. ambiguous requests
7. missing tables or columns
8. unsafe SQL requests
9. provider failures
10. schema-heavy queries

Each case should record the expected behavior and the observed result. Do not report an accuracy percentage unless the dataset, evaluator, and methodology are reproducible.

## Suggested benchmark record

```json
{
  "id": "revenue_by_region_001",
  "question": "Show revenue by region for Q2",
  "expected_tables": ["orders", "customers"],
  "expected_behavior": "read_only_sql",
  "expected_columns": ["region", "revenue"],
  "notes": "Join orders to customers before aggregation"
}
```

## Failure analysis

When a case fails, classify the failure instead of only recording a score:

- intent failure
- retrieval failure
- schema grounding failure
- SQL generation failure
- validation failure
- execution failure
- provider failure
- timeout / latency failure

This makes the benchmark useful for engineering decisions and regression testing.

## Reporting

Future benchmark results should report the dataset version, evaluator version, model/provider configuration, sample count, and measurement date. Compare changes against a defined baseline rather than reporting isolated percentages.
