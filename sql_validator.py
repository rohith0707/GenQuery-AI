# sql_validator.py
import re
import sqlparse

DANGEROUS_KEYWORDS = [
    r"\bDELETE\b",
    r"\bUPDATE\b",
]
# Reverted restriction: allow broader Snowflake read-only statements (SHOW, DESCRIBE, CALL for UDFs, etc.)
# Only DELETE and UPDATE are blocked per user request.

def sanitize_sql(sql: str) -> str:
    # Remove comments
    s = re.sub(r"--.*", "", sql)
    s = re.sub(r"/\*[\s\S]*?\*/", "", s)
    # Keep only first statement (avoid stacked statements)
    parts = [p.strip() for p in s.split(";") if p.strip()]
    return parts[0] if parts else ""

def contains_dangerous(sql: str) -> bool:
    s = sql.upper()
    for kw in DANGEROUS_KEYWORDS:
        if re.search(kw, s):
            return True
    return False

def validate_sql_safe(sql: str) -> (bool, str):
    clean = sanitize_sql(sql)
    if not clean:
        return False, "SQL is empty after sanitization."
    if contains_dangerous(clean):
        return False, "Statement contains a blocked keyword (DELETE/UPDATE)."
    # No prefix restriction: permit broader Snowflake read-only operations.
    return True, ""
