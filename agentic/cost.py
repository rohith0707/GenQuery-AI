"""Pre-execution risk and cost heuristics; Snowflake EXPLAIN can replace this later."""
import re
def assess_sql(sql):
    s=sql.upper(); joins=len(re.findall(r"\\bJOIN\\b",s)); ctes=len(re.findall(r"\\bWITH\\b",s)); has_limit=bool(re.search(r"\\bLIMIT\\s+\\d+",s)); score=0
    score += min(joins*15,45); score += min(ctes*5,15); score += 0 if has_limit else 20
    risk="low" if score<25 else "medium" if score<55 else "high"
    return {"risk":risk,"score":min(score,100),"joins":joins,"ctes":ctes,"has_limit":has_limit,"recommendation":"Add a bounded LIMIT or run EXPLAIN before execution." if not has_limit else "Plan has a result bound."}
