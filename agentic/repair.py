"""Bounded SQL repair loop using the existing provider layer."""
def repair_once(question,sql_error,schema_text=""):
    from langchain_agent import generate_sql
    prompt=(question+"\\n\\nPrevious SQL failed validation/execution. Repair it.\\n"+str(sql_error)+"\\nReturn a corrected read-only query only.")
    return generate_sql(prompt,schema_text)
