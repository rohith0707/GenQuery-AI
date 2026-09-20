from agentic.planner import QueryPlanner
from agentic.validators import validate_plan

def test_planner_creates_structured_ir():
    p=QueryPlanner().plan("revenue from enterprise customers in Hyderabad last quarter",["customers ↔ orders"])
    assert p.intent=="analytical_query"
    assert "revenue" in p.metrics
    assert "customer" in p.entities
    assert p.filters and p.join_paths

def test_validator_blocks_unresolved_multi_entity_join():
    p=QueryPlanner().plan("revenue from customers")
    p.entities=["customer","order"]
    report=validate_plan(p)
    assert not report.passed
