"""Semantic graph helpers for the Agent Workspace."""
def build_semantic_graph(plan: dict) -> dict:
    nodes, edges = [], []
    for entity in plan.get("entities", []): nodes.append({"id": entity, "label": entity.title(), "kind": "entity"})
    for metric in plan.get("metrics", []):
        mid = "metric:" + metric
        nodes.append({"id": mid, "label": metric.title(), "kind": "metric"})
        if plan.get("entities"): edges.append({"source": plan["entities"][0], "target": mid, "label": "measures"})
    for i, join in enumerate(plan.get("join_hints", [])): nodes.append({"id": "join:"+str(i), "label": join, "kind": "relationship"})
    return {"nodes": nodes, "edges": edges}

def context_summary(plan: dict) -> str:
    lines = ["Intent: " + str(plan.get("intent"))]
    if plan.get("metrics"): lines.append("Metrics: " + ", ".join(plan["metrics"]))
    if plan.get("entities"): lines.append("Entities: " + ", ".join(plan["entities"]))
    if plan.get("filters"): lines.append("Filters: " + "; ".join(plan["filters"]))
    if plan.get("join_hints"): lines.append("Join paths: " + "; ".join(plan["join_hints"]))
    return "\n".join(lines)