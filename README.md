# GenQuery-AI

> Natural language → safe, schema-aware SQL for Snowflake.

GenQuery-AI explores how to build a natural-language-to-SQL system as a **reliable application**, not just an LLM prompt.

The core pipeline is:

```text
User question
     ↓
Intent understanding
     ↓
Schema retrieval
     ↓
SQL generation
     ↓
Deterministic validation
     ↓
Read-only execution
     ↓
Result + telemetry
```

## Why this project exists

A useful SQL agent has to solve more than generation quality. It needs to handle schema grounding, unsafe output, provider failures, latency, caching, observability, and regression testing.

This repository is a practical exploration of those engineering boundaries.

## Engineering surface

- **Schema-aware RAG** — retrieve relevant tables/columns before generation
- **Multi-provider inference** — cloud and local providers with fallback support
- **SQL safety** — read-only policy, DDL/DML blocking, multi-statement checks
- **Query recovery** — validation and regeneration paths for failed queries
- **Semantic caching** — reduce repeated inference for similar requests
- **Telemetry** — provider, latency, cache, execution and feedback signals
- **Evaluation** — regression methodology for SQL correctness and system behavior
- **Snowflake integration** — schema introspection and controlled execution

## Architecture

```text
                       ┌─────────────────┐
                       │ Natural Language│
                       │     Question    │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Intent / Context│
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Schema Retrieval│
                       │      (RAG)      │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │  LLM Provider   │
                       │ + fallback path │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ SQL Validation  │
                       │  + safety gate  │
                       └────────┬────────┘
                                │
                         safe SQL only
                                │
                                ▼
                       ┌─────────────────┐
                       │    Snowflake    │
                       │  read-only role │
                       └────────┬────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Result + Metrics│
                       └─────────────────┘
```

## Local setup

### Requirements

- Python 3.8+
- Snowflake account with a least-privilege read-only role
- At least one supported LLM provider, or a local provider such as Ollama

```bash
git clone https://github.com/rohith0707/GenQuery-AI.git
cd GenQuery-AI
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

On Windows, copy `.env.example` to `.env` manually if `cp` is unavailable.

## Configuration

`.env.example` contains placeholders only. Never commit real API keys or database credentials.

Use a dedicated **read-only** Snowflake role. The application should not be given write privileges merely because generated SQL comes from a trusted-looking prompt.

## Evaluation

The project treats evaluation as an engineering artifact. See [`docs/EVALUATION.md`](docs/EVALUATION.md).

The benchmark methodology separates:

- SQL validity
- task correctness
- schema grounding
- safety
- robustness
- latency
- cost

Failed cases should be categorized by failure mode rather than hidden behind a single accuracy number.

## Architecture decisions

See [`docs/ARCHITECTURE_DECISIONS.md`](docs/ARCHITECTURE_DECISIONS.md) for the reasoning behind schema retrieval, validation, read-only execution, provider fallback, telemetry, and system-level evaluation.

## Security

The application is designed around least privilege:

1. Generated SQL is validated before execution.
2. DDL/DML operations are blocked.
3. Multi-statement execution is rejected.
4. Snowflake should use a read-only role.
5. Credentials belong in environment variables, never source control.
6. Query-result limits reduce accidental large reads.

This is application-level protection, not a substitute for Snowflake network, identity, permission, and monitoring controls.

## Current limitations

This is an engineering project, not a claim of perfect text-to-SQL accuracy. Known limitations include:

- model output remains probabilistic
- retrieval errors can propagate into SQL generation
- SQL validation is necessarily incomplete compared with a full database security boundary
- query cost is not currently predicted before execution
- provider behavior varies across models and versions

The goal is to make those failure modes measurable and progressively reduce them.

## Roadmap

- [ ] Public regression dataset with versioned cases
- [ ] Automated benchmark runner
- [ ] Model/provider comparison dashboard
- [ ] Execution-cost estimation
- [ ] Better retrieval evaluation
- [ ] CI evaluation gate for regression cases
- [ ] FastAPI service layer alongside the Streamlit UI

## License

No license is currently declared. Do not assume the code is licensed for unrestricted reuse.
