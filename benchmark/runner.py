"""Benchmark runner with static regression mode and optional live execution."""
from __future__ import annotations
import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from agentic.engine import AgenticQueryEngine

ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "datasets" / "golden.jsonl"


@dataclass
class CaseResult:
    id: str
    question: str
    difficulty: str
    passed: bool
    metric_ok: bool
    entity_ok: bool
    plan_ok: bool
    validation_ok: bool
    sql_compiled: bool
    execution_ok: bool
    answer_artifact_ok: bool
    answer_type: str
    latency_ms: float
    error: str = ""


def load_cases(path: Path, limit: int | None = None):
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return rows[:limit] if limit else rows


def run(cases, live=False, compile_sql=True):
    engine = AgenticQueryEngine()
    results = []
    for case in cases:
        start = time.perf_counter()
        execution_ok = not live
        answer_artifact_ok = not live
        answer_type = ""
        error = ""
        try:
            result = engine.analyze(case["question"])
            metric_ok = case.get("expected_metric") in result.plan.metrics
            entity_ok = all(
                any(e in actual or actual in e for actual in result.plan.entities)
                for e in case.get("expected_entities", [])
            )
            plan_ok = bool(result.plan.intent and result.plan.confidence >= 0)
            validation_ok = result.validation.passed

            if compile_sql and validation_ok and not result.sql:
                result = engine.compile(result)
            sql_compiled = bool(result.sql)

            if live and sql_compiled:
                from snowflake_client import run_query
                from agentic.answer import build_answer

                df = run_query(result.sql)
                artifact = build_answer(
                    case["question"],
                    df,
                    plan=result.plan,
                    evidence=result.evidence,
                )
                execution_ok = True
                answer_artifact_ok = bool(
                    artifact.answer_type and artifact.summary and artifact.evidence
                )
                answer_type = artifact.answer_type

            passed = metric_ok and entity_ok and plan_ok and validation_ok
            if compile_sql:
                passed = passed and sql_compiled and execution_ok and answer_artifact_ok

        except Exception as exc:
            metric_ok = entity_ok = plan_ok = validation_ok = sql_compiled = False
            passed = False
            execution_ok = False
            answer_artifact_ok = False
            answer_type = ""
            error = str(exc)

        results.append(
            CaseResult(
                case["id"],
                case["question"],
                case.get("difficulty", "unknown"),
                passed,
                metric_ok,
                entity_ok,
                plan_ok,
                validation_ok,
                sql_compiled,
                execution_ok,
                answer_artifact_ok,
                answer_type,
                (time.perf_counter() - start) * 1000,
                error,
            )
        )
    return results


def summary(results):
    n = len(results) or 1

    def pct(key):
        return round(100 * sum(bool(getattr(r, key)) for r in results) / n, 2)

    lat = sorted(r.latency_ms for r in results)
    return {
        "cases": len(results),
        "pass_rate": pct("passed"),
        "metric_accuracy": pct("metric_ok"),
        "entity_accuracy": pct("entity_ok"),
        "plan_validity": pct("plan_ok"),
        "validation_pass_rate": pct("validation_ok"),
        "sql_compile_rate": pct("sql_compiled"),
        "execution_accuracy": pct("execution_ok"),
        "answer_artifact_rate": pct("answer_artifact_ok"),
        "latency_p50_ms": round(lat[(len(lat) - 1) // 2], 2) if lat else 0,
        "failures": [asdict(r) for r in results if not r.passed],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--static",
        action="store_true",
        help="Skip LLM SQL compilation; validate deterministic planning stages only",
    )
    parser.add_argument("--output", default="benchmark-report.json")
    args = parser.parse_args()

    if args.live and os.getenv("GENQUERY_BENCHMARK_LIVE") != "1":
        raise SystemExit(
            "Refusing live execution: set GENQUERY_BENCHMARK_LIVE=1 explicitly."
        )

    results = run(
        load_cases(Path(args.dataset), args.limit),
        args.live,
        compile_sql=not args.static,
    )
    report = summary(results)
    Path(args.output).write_text(
        json.dumps(
            {"summary": report, "results": [asdict(r) for r in results]},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["pass_rate"] >= 80 else 1


if __name__ == "__main__":
    raise SystemExit(main())
