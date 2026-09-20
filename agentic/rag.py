"""Adaptive RAG adapter over GenQuery's existing RAG engine."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

def adaptive_retrieve(question: str, complexity: dict[str, Any] | None = None):
    from .contracts import RetrievalBundle
    try:
        from rag_engine import get_rag_engine
        engine = get_rag_engine()
    except Exception as exc:
        return {}, [{"source":"rag_engine","detail":f"unavailable: {exc}"}]
    if not getattr(engine, "is_initialized", False):
        return {}, [{"source":"rag_engine","detail":"not initialized"}]
    complexity=complexity or {}
    jobs={"schema":lambda: engine.retrieve(question, top_k=8),"cache":lambda: engine.find_similar(question)}
    if complexity.get("examples"): jobs["query_memory"]=lambda: engine.get_similar(question, top_k=3)
    raw={}; sources=[]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        fm={pool.submit(fn):name for name,fn in jobs.items()}
        for fut in as_completed(fm):
            name=fm[fut]
            try: raw[name]=fut.result(); sources.append({"source":name,"detail":"retrieved"})
            except Exception as exc: raw[name]=[]; sources.append({"source":name,"detail":f"failed: {exc}"})
    return raw,sources

def normalize_retrieval(raw, sources):
    from .contracts import RetrievalBundle
    cache=raw.get("cache")
    cached_sql,confidence=(cache if isinstance(cache,tuple) else (None,0.0))
    return RetrievalBundle(schema=raw.get("schema") or [],examples=raw.get("query_memory") or [],cached_sql=cached_sql,cache_confidence=float(confidence or 0),sources=sources)
