# GenQuery-AI

> Natural language → semantic reasoning → validated SQL → decision-ready answer, with evidence.

GenQuery-AI explores how to build a natural-language analytics system as a **reliable agentic application**, not just an LLM prompt. Snowflake is the controlled execution layer; the customer-facing product is the interpreted answer.

The core pipeline is:

```text
Business question
      ↓
Intent / Semantic resolution
      ↓
Adaptive RAG
      ↓
Semantic Graph
      ↓
Query Plan IR
      ↓
Validation / Safety
      ↓
SQL Compiler
      ↓
Snowflake (controlled execution)
      ↓
Result Interpreter
      ↓
Answer Planner
      ↓
Decision-ready Answer
      ├── Executive / KPI
      ├── Chart / Trend
      ├── Comparison
      ├── Insight / anomaly
      ├── Table
      └── Raw data / SQL for audit
      ↓
Evidence
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
- **Evaluation** — regression methodology for SQL correctness, answer generation and system behavior
- **Answer Intelligence** — decision-ready summaries, KPIs, charts, trends, comparisons and insights
- **Evidence** — customer claims remain linked to structured retrieval/plan/execution artifacts
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

- Python 3.10+ (Python 3.11 recommended)
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

## Customer Answer Intelligence

The raw Snowflake DataFrame is treated as an internal execution artifact. The customer receives an Answer Artifact that can be rendered as:

| View | Typical question |
| --- | --- |
| Executive | What happened to revenue? |
| KPI | What is revenue? |
| Chart | Show revenue by region |
| Trend | How has revenue changed over time? |
| Comparison | Compare Hyderabad vs Bangalore |
| Insight | Why did revenue fall? |
| Table | Show grouped results |
| Raw | Show underlying data / SQL |

The answer layer is deterministic today: it inspects the result shape, selects an appropriate view, produces KPIs/comparisons/trend data, flags simple statistical outliers, and keeps evidence attached. Deeper causal reasoning is intentionally not claimed without supporting evidence.

The Agent Workspace lets an operator switch between customer-facing views while retaining evidence and an explicit raw-data/audit path.

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
- query cost is currently a heuristic before execution rather than Snowflake EXPLAIN-backed
- answer interpretation is deterministic and deliberately conservative today
- provider behavior varies across models and versions

The goal is to make those failure modes measurable and progressively reduce them.

## Roadmap

- [ ] Public regression dataset with versioned cases
- [x] Automated benchmark runner
- [ ] Model/provider comparison dashboard
- [ ] Execution-cost estimation with Snowflake EXPLAIN
- [ ] Better retrieval evaluation
- [x] CI evaluation gate for regression cases
- [x] Container deployment path
- [x] Customer-facing answer artifacts
- [ ] FastAPI service layer alongside the Streamlit UI

## Latest main commits

Latest main commits now include the benchmark/deployment loop and customer-answer intelligence:

| Commit | Change |
| --- | --- |
| 6c36473e | docs: document answer intelligence benchmarks |
| 68a18aac | docs: document answer intelligence and latest main commits |
| fecef027 | test: cover answer benchmark metrics |
| e3074372 | feat: benchmark customer answer artifacts |
| d818e73f | feat: render customer-facing answer views |
| 74a332e8 | feat: support multiple answer render views |
| 23d56e51 | feat: add answer artifact contract |
| f8e1215c | test: evaluate customer-facing answer artifacts |
| 95fb6be8 | feat: add customer answer intelligence |
| 7f033137 | deploy: add container health check |
| 8bb47801 | ci: run benchmark regression without model dependency |
| 4781f9bb | feat: link benchmark workspace |
| 2f302029 | fix: separate static and live benchmark modes |

## License

No license is currently declared. Do not assume the code is licensed for unrestricted reuse.


## Agentic Agent Workspace

The current main branch includes an inspectable agentic workflow:

**Question → Adaptive RAG → Semantic Graph → Query Plan IR → Validation → SQL Compiler → Execution → Result Interpretation → Answer Artifact → Evidence**

Open **Agent Workspace** from the Streamlit pages to inspect the structured plan, retrieval sources, semantic graph, validation gates, compiled SQL, customer-facing answer views and optional raw-data/audit output.
