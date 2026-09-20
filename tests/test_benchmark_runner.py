from benchmark.runner import load_cases, summary, CaseResult
from pathlib import Path


def test_golden_dataset_loads():
    cases = load_cases(Path("benchmark/datasets/golden.jsonl"))
    assert len(cases) == 20
    assert cases[0]["expected_metric"] == "revenue"


def test_summary_handles_results():
    row = CaseResult(
        "1", "q", "simple", True,
        True, True, True, True, True, True, True, "kpi", 10.0
    )
    report = summary([row])
    assert report["pass_rate"] == 100.0
    assert report["sql_compile_rate"] == 100.0
    assert report["answer_artifact_rate"] == 100.0
