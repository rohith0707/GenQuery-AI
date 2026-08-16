# Architecture Decisions

This document records decisions that shape GenQuery-AI as a production-oriented natural-language-to-SQL system.

## Decision 1 — Retrieve schema before generation

**Decision:** Ground SQL generation in retrieved schema context.

**Why:** An LLM cannot reliably infer an enterprise database schema from the question alone. Retrieval narrows the context to relevant tables and columns.

**Trade-off:** Retrieval introduces another failure mode. Incorrect retrieval can produce confident but invalid SQL, so retrieval quality must be evaluated separately.

## Decision 2 — Validate before execution

**Decision:** Generated SQL passes through a validation layer before reaching Snowflake.

**Why:** An LLM should not be treated as a trusted database client. The application needs deterministic controls around allowed operations.

**Trade-off:** Conservative validation can reject legitimate queries, so validation rules should be tested against representative workloads.

## Decision 3 — Prefer read-only execution

**Decision:** The public configuration uses a least-privilege read-only Snowflake role.

**Why:** Natural-language-to-SQL systems operate on model-generated code. Limiting database permissions reduces blast radius if generation or validation fails.

## Decision 4 — Support provider fallback

**Decision:** Multiple model providers can be configured with fallback behavior.

**Why:** Provider availability, latency, and model behavior can vary.

**Trade-off:** Fallback can change model behavior and cost. Provider selection should therefore be observable.

## Decision 5 — Track telemetry

**Decision:** Record provider, latency, cache behavior, execution statistics, and user feedback.

**Why:** Without telemetry, improving an LLM application becomes guesswork.

## Decision 6 — Evaluate the system, not just the model

**Decision:** Regression testing includes generation, schema grounding, validation, execution behavior, and failure categories.

**Why:** A higher model benchmark score does not guarantee a better end-to-end SQL product.
