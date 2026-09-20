"""Agentic orchestration over GenQuery's existing RAG, provider and safety layers."""
from .contracts import AgentResult,AgentTrace
from .planner import QueryPlanner
from .graph import SemanticGraph
from .rag import adaptive_retrieve,normalize_retrieval
from .validators import validate_plan,validate_sql
class AgenticQueryEngine:
    def __init__(self): self.planner=QueryPlanner()
    def analyze(self,question,schema_text=""):
        traces=[AgentTrace("intent","Planner Agent","completed","Extracted intent and candidate entities")]
        raw,sources=adaptive_retrieve(question,{"examples":True})
        retrieval=normalize_retrieval(raw,sources)
        traces.append(AgentTrace("retrieve","Adaptive RAG Agent","completed","Parallel retrieval across schema, query memory and cache",[x["source"] for x in sources]))
        initial=self.planner.plan(question)
        graph=SemanticGraph(retrieval.schema)
        joins=graph.find_join_paths(initial.entities)
        plan=self.planner.plan(question,joins)
        traces.append(AgentTrace("resolve","Semantic Resolver","completed","Resolved entities and candidate join paths",joins))
        validation=validate_plan(plan)
        traces.append(AgentTrace("validate","Plan Validator","completed" if validation.passed else "blocked","Validated Query Plan IR",list(validation.checks)))
        result=AgentResult(question,plan,retrieval,validation,traces=traces)
        if retrieval.cached_sql and retrieval.cache_confidence>=.90:
            ok,_,clean=validate_sql(retrieval.cached_sql)
            if ok:
                result.sql=clean; result.traces.append(AgentTrace("compile","SQL Compiler","cache-hit","Reused validated semantic-cache SQL"))
        return result
    def compile(self,result,schema_text=""):
        if result.sql or not result.validation.passed: return result
        from langchain_agent import generate_sql
        context=schema_text
        if result.retrieval.schema: context += "\\nRetrieved schema:\\n"+"\\n".join(x.get("compact_schema","") for x in result.retrieval.schema)
        try: sql=generate_sql(result.question,context)
        except Exception as exc:
            result.validation.errors.append(str(exc)); result.validation.passed=False; result.traces.append(AgentTrace("compile","SQL Compiler","failed",str(exc))); return result
        ok,msg,clean=validate_sql(sql)
        if not ok:
            result.validation.errors.append(msg); result.validation.passed=False; result.traces.append(AgentTrace("compile","SQL Compiler","blocked",msg)); return result
        result.sql=clean
        result.evidence=[{"type":"retrieval","source":x["source"],"detail":x["detail"]} for x in result.retrieval.sources]
        result.evidence.append({"type":"query_plan","source":"semantic_plan","detail":str(result.plan.to_dict())})
        result.traces.append(AgentTrace("compile","SQL Compiler","completed","Compiled validated Query Plan into SQL"))
        return result
