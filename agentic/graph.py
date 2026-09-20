"""Semantic/join graph derived from retrieved schema metadata."""
from __future__ import annotations
import re
class SemanticGraph:
    def __init__(self,tables=None):
        self.nodes=[]; self.edges=[]
        for t in tables or []:
            name=t.get("table_name","")
            if not name: continue
            self.nodes.append({"id":name,"label":name,"kind":"table"})
            compact=t.get("compact_schema","")
            for col in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\s+[A-Za-z]",compact):
                self.nodes.append({"id":f"{name}.{col}","label":col,"kind":"column","table":name})
        self._infer_relationships()
    def _infer_relationships(self):
        tables=[n["id"] for n in self.nodes if n["kind"]=="table"]
        cols=[n for n in self.nodes if n["kind"]=="column"]
        for col in cols:
            cname=col["label"].lower()
            if not cname.endswith("_id"): continue
            stem=cname[:-3]
            for table in tables:
                base=table.lower().split(".")[-1].rstrip("s")
                if stem in {base,base.replace("_","")}:
                    target=f"{table}.{stem}_id"
                    if target != col["id"] and any(x["id"]==target for x in cols): self.edges.append({"source":col["id"],"target":target,"label":"possible_fk"})
    def find_join_paths(self,entities):
        tables=[n["id"] for n in self.nodes if n["kind"]=="table"]
        hits=[]
        for entity in entities:
            found=next((t for t in tables if entity.lower() in t.lower() or entity.lower().rstrip("s") in t.lower()),None)
            if found: hits.append(found)
        if len(hits)>=2:
            for edge in self.edges:
                if any(edge["source"].startswith(x+".") for x in hits) and any(edge["target"].startswith(x+".") for x in hits): return [f"{hits[0]} ↔ {hits[1]} via {edge['source'].split('.')[-1]}"]
        return []
    def to_dict(self): return {"nodes":self.nodes,"edges":self.edges}
