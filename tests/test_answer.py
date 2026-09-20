import pandas as pd
from agentic.answer import build_answer


def test_single_metric_becomes_kpi():
    artifact = build_answer("What is revenue?", pd.DataFrame({"revenue": [8700000]}))
    assert artifact.answer_type == "kpi"
    assert artifact.kpis[0]["raw_value"] == 8700000


def test_grouped_metric_becomes_chart():
    artifact = build_answer("Show revenue by region", pd.DataFrame({"region": ["HYD", "BLR"], "revenue": [10, 8]}))
    assert artifact.answer_type == "chart"
    assert artifact.visualization["x"] == "region"


def test_why_question_becomes_insight():
    artifact = build_answer("Why did revenue fall?", pd.DataFrame({"segment": ["A", "B"], "revenue": [10, 7]}))
    assert artifact.answer_type == "insight"
    assert artifact.insights


def test_empty_result_is_safe():
    artifact = build_answer("Show revenue", pd.DataFrame(columns=["revenue"]))
    assert artifact.answer_type == "empty"
    assert artifact.row_count == 0
