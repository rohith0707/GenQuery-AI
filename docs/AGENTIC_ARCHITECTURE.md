# GenQuery Agentic Architecture

GenQuery now exposes an inspectable Agent Workspace instead of treating NL→SQL as a single LLM call.

## Runtime contract
**Retrieve → Resolve → Reason → Plan → Validate → Compile → Execute → Prove**

The Query Plan IR is the architectural boundary. Agents and retrieval systems resolve semantics, but only the SQL Compiler should convert a validated plan into executable SQL.

## Engineering tracks
- Adaptive RAG: choose schema, metric, business-context and query-memory retrieval based on query complexity.
- Semantic graph: make entities, metrics and relationships explicit and inspectable.
- Agent planner: produce structured intent and Query Plan IR before SQL generation.
- Validation and repair: make semantic, safety and cost checks first-class gates.
- Evidence: expose metric definitions, tables, joins, filters and execution metadata without exposing private model chain-of-thought.

## Production next steps
1. Replace heuristic extraction with structured LLM planner output.
2. Connect existing RAG stores to schema and metric retrieval agents.
3. Persist graph metadata and join confidence.
4. Add an error-memory repair loop.
5. Add retrieval, plan and execution metrics to CI.
6. Add pre-execution cost estimation.