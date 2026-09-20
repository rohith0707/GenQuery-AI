"""Semantic and SQL validation gates."""
from .contracts import QueryPlan,ValidationReport
def validate_plan(plan:QueryPlan):
    checks={"intent_resolved":bool(plan.intent),"entity_resolved":bool(plan.entities),"metric_resolved":bool(plan.metrics),"join_path_resolved":not len(plan.entities)>1 or bool(plan.join_paths)}
    errors=[]; warnings=[]
    if not checks["metric_resolved"]: warnings.append("No explicit metric detected; clarification may be required.")
    if not checks["join_path_resolved"]: errors.append("Multiple entities detected but no join path was resolved.")
    return ValidationReport(not errors,checks,errors,warnings)
def validate_sql(sql):
    from sql_validator import sanitize_sql,validate_sql_safe
    clean=sanitize_sql(sql); ok,msg=validate_sql_safe(clean); return ok,msg,clean
