"""Stable contracts exchanged between GenQuery agents."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
@dataclass
class RetrievalBundle:
    schema: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    cached_sql: str | None = None
    cache_confidence: float = 0.0
    sources: list[dict[str, str]] = field(default_factory=list)
@dataclass
class QueryPlan:
    intent: str
    entities: list[str]
    metrics: list[str]
    dimensions: list[str]
    filters: list[str]
    time_range: str | None
    join_paths: list[str]
    assumptions: list[str] = field(default_factory=list)
    confidence: float = 0.0
    def to_dict(self): return asdict(self)
@dataclass
class ValidationReport:
    passed: bool
    checks: dict[str, bool]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    def to_dict(self): return asdict(self)
@dataclass
class AgentTrace:
    stage: str
    agent: str
    status: str
    detail: str
    evidence: list[str] = field(default_factory=list)
    def to_dict(self): return asdict(self)
@dataclass
class AgentResult:
    question: str
    plan: QueryPlan
    retrieval: RetrievalBundle
    validation: ValidationReport
    sql: str = ""
    traces: list[AgentTrace] = field(default_factory=list)
    repair_count: int = 0
    evidence: list[dict[str, str]] = field(default_factory=list)
    cost: dict[str, Any] = field(default_factory=dict)
    answer: dict[str, Any] = field(default_factory=dict)
    def to_dict(self): return asdict(self)
