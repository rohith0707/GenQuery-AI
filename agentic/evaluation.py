"""Small deterministic evaluation helpers for agentic artifacts."""
def evaluate_result(result):
    return {"plan_present":bool(result.plan),"retrieval_present":bool(result.retrieval.sources),"validation_passed":result.validation.passed,"sql_compiled":bool(result.sql),"evidence_present":bool(result.evidence),"repair_count":result.repair_count}
