"""Query planner: question -> structured semantic QueryPlan."""
from __future__ import annotations
import re
from .contracts import QueryPlan
class QueryPlanner:
    METRIC_TERMS={"revenue":"revenue","sales":"revenue","gmv":"revenue","count":"count","average":"average","avg":"average"}
    ENTITY_TERMS={"customer":["customer","client","account"],"order":["order","orders","purchase","transaction"],"product":["product","sku","item"],"location":["city","region","location","country"]}
    def plan(self,question,join_paths=None):
        q=question.lower(); metrics=[]
        for term,metric in self.METRIC_TERMS.items():
            if re.search(r"\\b"+re.escape(term)+r"\\b",q) and metric not in metrics: metrics.append(metric)
        entities=[]
        for entity,terms in self.ENTITY_TERMS.items():
            if any(re.search(r"\\b"+re.escape(t)+r"\\b",q) for t in terms): entities.append(entity)
        if not entities: entities=["business entity"]
        filters=[]
        for city in ("hyderabad","bangalore","bengaluru","mumbai","delhi","chennai"):
            if city in q: filters.append(f"location = {city.title()}")
        for segment in ("enterprise","smb","consumer"):
            if segment in q: filters.append(f"customer_segment = {segment}")
        time_range=None
        for phrase,label in (("last quarter","previous quarter"),("previous quarter","previous quarter"),("this quarter","current quarter"),("last month","previous month"),("last year","previous year")):
            if phrase in q: time_range=label; filters.append(f"date = {label}"); break
        dimensions=[term.replace("by ","").replace("per ","") for term in ("by region","by city","by customer","by product","per customer","per region") if term in q]
        confidence=.62+(.12 if metrics else 0)+(.08 if filters else 0)+(.08 if join_paths else 0)+(.05 if dimensions else 0)
        return QueryPlan("analytical_query" if metrics else "data_exploration",entities,metrics,dimensions,filters,time_range,join_paths or [],["metric semantics require confirmation"] if metrics else ["metric not explicit"],round(min(confidence,.96),2))
