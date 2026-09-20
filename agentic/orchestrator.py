"""Provider-agnostic, inspectable query planning primitives."""
from __future__ import annotations
import re
from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass
class PlanStep:
    id: str
    agent: str
    action: str
    status: str = "ready"
    evidence: list[str] = field(default_factory=list)

@dataclass
class AgentPlan:
    question: str
    intent: str
    entities: list[str]
    metrics: list[str]
    filters: list[str]
    time_range: str | None
    retrieval: list[str]
    join_hints: list[str]
    steps: list[PlanStep]
    confidence: float
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _has(q: str, *terms: str) -> bool:
    return any(t in q for t in terms)

def build_agent_plan(question: str, retrieved_context: dict[str, Any] | None = None) -> AgentPlan:
    """Build an inspectable plan; LLMs can enrich these artifacts later."""
    q = question.strip().lower()
    context = retrieved_context or {}
    metrics = []
    if _has(q, "revenue", "sales", "income", "gmv"): metrics.append("revenue")
    elif _has(q, "count", "number of", "how many"): metrics.append("count")
    elif _has(q, "average", "avg", "mean"): metrics.append("average")
    entities = []
    for name, terms in {"customer": ("customer","client","account"), "order": ("order","orders","purchase","transaction"), "product": ("product","sku","item"), "location": ("city","region","location","country")}.items():
        if _has(q, *terms): entities.append(name)
    if not entities: entities = ["business entity"]
    filters = []
    for city in ("hyderabad","bangalore","bengaluru","mumbai","delhi","chennai"):
        if city in q: filters.append("location = " + city.title())
    for segment in ("enterprise","smb","consumer"):
        if segment in q: filters.append("customer_segment = " + segment)
    time_range = None
    for phrase, label in (("last quarter","previous quarter"),("previous quarter","previous quarter"),("this quarter","current quarter"),("last month","previous month"),("last year","previous year"),("previous year","previous year")):
        if phrase in q: time_range = label; filters.append("date = " + label); break
    retrieval = ["schema_rag"]
    if metrics: retrieval.append("metric_rag")
    if len(entities) > 1: retrieval.append("join_graph")
    if filters: retrieval.append("business_context_rag")
    if context.get("examples"): retrieval.append("query_memory")
    join_hints = []
    if {"customer","order"}.issubset(set(entities)): join_hints.append("customer.customer_id → order.customer_id")
    if {"product","order"}.issubset(set(entities)): join_hints.append("order.product_id → product.product_id")
    steps = [
        PlanStep("intent","Planner Agent","Classify intent and extract entities"),
        PlanStep("retrieve","Adaptive RAG Agent","Retrieve only required semantic context", evidence=retrieval),
        PlanStep("resolve","Semantic Resolver","Resolve metrics, dimensions, filters and joins"),
        PlanStep("plan","Query Planner","Build structured Query Plan IR before SQL"),
        PlanStep("validate","Plan Validator","Check semantic completeness and ambiguity"),
        PlanStep("compile","SQL Compiler","Compile validated IR into Snowflake SQL"),
        PlanStep("guard","Safety + Cost Gate","Enforce read-only policy and execution limits"),
        PlanStep("execute","Execution Agent","Execute only after validation passes"),
        PlanStep("prove","Evidence Agent","Attach sources, assumptions and execution metadata"),
    ]
    score = 0.72 + (0.08 if metrics else 0) + (0.05 if filters else 0) + (0.05 if join_hints else 0) + (0.04 if len(entities) > 1 else 0)
    return AgentPlan(question, "analytical_query" if metrics else "data_exploration", entities, metrics, filters, time_range, retrieval, join_hints, steps, round(min(score,0.96),2))