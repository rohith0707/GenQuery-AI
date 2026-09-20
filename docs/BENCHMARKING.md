# GenQuery Benchmarking and Deployment

## Engineering loop

1. Change code.
2. Run python -m pytest -q.
3. Run python -m benchmark.runner --limit 20 --static.
4. Inspect benchmark-report.json and classify failures by stage.
5. Fix the smallest root cause.
6. Repeat until the regression gate is green.
7. Deploy the same tested commit as a container.
8. Run live benchmarks only against a read-only benchmark Snowflake environment.

## Benchmark stages

The benchmark measures:

- metric accuracy
- entity accuracy
- Query Plan validity
- validation pass rate
- SQL compilation
- live SQL execution
- answer-artifact generation
- latency
- case-level failures

The live path evaluates the complete product boundary:

question -> agentic plan -> SQL -> Snowflake result -> AnswerArtifact

The raw Snowflake result is not considered the customer-facing success criterion by itself.

## Customer answer evaluation

An executed query is considered answer-ready only when GenQuery can produce an Answer Artifact containing:

- an answer type
- a human-readable summary
- structured evidence
- a confidence signal

The workspace can render the artifact as executive, KPI, chart, trend, comparison, insight, table, or raw-data views.

This does not mean every generated insight is causal. The current interpreter is intentionally conservative and labels limitations when the result alone cannot establish a causal driver.

## Static CI mode

CI uses:

python -m benchmark.runner --limit 20 --static

Static mode evaluates deterministic planner/validation stages and does not require LLM or Snowflake secrets.

## Live mode

Live execution is opt-in:

GENQUERY_BENCHMARK_LIVE=1 python -m benchmark.runner --limit 20 --live

Use only a staging/benchmark account, dedicated read-only Snowflake role, and an isolated warehouse/database. Never point the benchmark runner at a production write-capable role.

## Container deployment

Build and run:

docker build -t genquery-ai .
docker run --env-file .env -p 8501:8501 genquery-ai

The image exposes Streamlit health checking through /_stcore/health.

Never bake .env or provider credentials into the image.

## Production evolution

The Streamlit deployment is appropriate for an internal/demo product. For higher scale, move agentic/ behind FastAPI and keep Streamlit as an operator/evaluation console. Benchmark jobs should run asynchronously so 100–500 question evaluations cannot block interactive user requests.
