# GenQuery Benchmarking and Deployment

## Engineering loop
1. Change code.
2. Run python -m pytest -q.
3. Run python -m benchmark.runner --limit 20.
4. Inspect benchmark-report.json and failures.
5. Fix the smallest root cause.
6. Repeat until green.
7. Deploy the same tested commit as a container.
8. Run live benchmarks only against a read-only benchmark Snowflake environment.

## Live benchmark safety
Set GENQUERY_BENCHMARK_LIVE=1 only in a benchmark/staging environment. Never point the benchmark at production credentials or a write-capable Snowflake role. The runner refuses live mode without the explicit flag.

## Container deployment
Build with docker build -t genquery-ai .
Run with docker run --env-file .env -p 8501:8501 genquery-ai.
Configure port 8501 and secret environment variables in the managed container platform. Never bake .env into the image.

## Production evolution
The Streamlit deployment is appropriate for an internal/demo product. For higher scale, move agentic/ behind FastAPI and keep Streamlit as an operator/evaluation console. Benchmark workers should run asynchronously so large benchmark runs cannot block interactive requests.
