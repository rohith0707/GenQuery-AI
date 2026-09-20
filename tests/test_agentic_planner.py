from agentic.orchestrator import build_agent_plan

def test_complex_question_builds_inspectable_plan():
    plan = build_agent_plan("What was our revenue from enterprise customers in Hyderabad last quarter?")
    assert plan.intent == "analytical_query"
    assert "revenue" in plan.metrics
    assert "customer" in plan.entities
    assert "order" in plan.entities
    assert "metric_rag" in plan.retrieval
    assert "join_graph" in plan.retrieval
    assert plan.join_hints
    assert plan.steps[-1].id == "prove"

def test_simple_question_still_has_a_plan():
    plan = build_agent_plan("How many customers do we have?")
    assert plan.metrics == ["count"]
    assert plan.steps