"""Business metric catalog used by the semantic planner."""
METRIC_CATALOG={
 "revenue":{"synonyms":["revenue","sales","gmv","total sales"],"expression":"SUM(order.amount)","grain":"order","description":"Monetary value of completed orders before business-specific exclusions."},
 "count":{"synonyms":["count","number of","how many"],"expression":"COUNT(*)","grain":"row","description":"Count of rows after requested filters."},
 "average":{"synonyms":["average","avg","mean"],"expression":"AVG(metric_value)","grain":"row","description":"Arithmetic mean of the selected numeric measure."}
}
def resolve_metric(name):
    n=name.lower()
    for key,meta in METRIC_CATALOG.items():
        if n==key or n in meta["synonyms"]: return {"name":key,**meta}
    return None
def context_for(metrics):
    return [resolve_metric(m) for m in metrics if resolve_metric(m)]
