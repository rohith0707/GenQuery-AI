# GenQuery Agentic Architecture

## Product output

GenQuery evolves from NL → SQL → result into:

**Question → Adaptive RAG → Semantic Resolution → Query Plan IR → Validation → SQL Compiler → Safety Gate → Execution → Evidence**

## Agent responsibilities

| Agent | Responsibility |
|---|---|
| Planner | Extract intent, entities, metrics, dimensions and time range |
| Adaptive RAG | Retrieve schema, query memory and semantic context in parallel |
| Semantic Resolver | Map language to entities and candidate relationships |
| Graph Resolver | Infer candidate foreign-key/join paths from retrieved schema |
| Query Planner | Produce deterministic Query Plan IR before SQL |
| Plan Validator | Block unresolved multi-entity plans and surface ambiguity |
| SQL Compiler | Convert validated IR to the existing SQL provider layer |
| Safety Gate | Reuse existing SQL sanitization and mutation protection |
| Execution Agent | Execute only after validation and compilation |
| Evidence Agent | Surface retrieval sources and the structured plan behind the result |

## RAG strategy

Existing rag_engine.py remains the source of truth. The agent layer does not create a second vector store. Retrieval tasks are parallelized and selected according to query complexity. Current sources are schema retrieval, semantic query cache and query-memory/few-shot retrieval.

## Semantic graph

The first graph is derived from retrieved schema metadata rather than inventing relationships. `_id` columns are used as candidate foreign-key signals. Production hardening should replace inference with explicit database constraints and a persisted business semantic layer.

## Safety boundary

Agents never directly execute arbitrary generated SQL. The Query Plan must pass semantic validation, SQL is compiled through the existing provider layer, and the existing sql_validator remains the execution safety boundary.

## UI principle

The Agent Workspace exposes structured artifacts, retrieval provenance, validation checks, SQL and execution results. It does not expose private model chain-of-thought.

## Next production increments

1. Add a first-class metric catalog with owner, grain and expression.
2. Persist graph relationships and join confidence.
3. Add error-memory and bounded repair loops.
4. Add pre-execution cost estimation with Snowflake EXPLAIN.
5. Add retrieval, plan and execution evaluation to CI.
