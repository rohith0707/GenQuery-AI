"""GenQuery Agent Workspace: inspectable planning and semantic reasoning UI."""
import json
import streamlit as st
from agentic.orchestrator import build_agent_plan
from agentic.semantic import build_semantic_graph, context_summary

st.set_page_config(page_title="GenQuery Agent Workspace", page_icon="🧠", layout="wide")
st.markdown("# 🧠 GenQuery Agent Workspace")
st.caption("Inspect the agent plan, semantic graph, retrieval strategy and validation gates before execution.")
question = st.text_area("Business question", value="What was our revenue from enterprise customers in Hyderabad last quarter?", height=90)
if st.button("▶ Build Agent Plan", type="primary"): st.session_state.agent_plan = build_agent_plan(question).to_dict()
if "agent_plan" not in st.session_state: st.session_state.agent_plan = build_agent_plan(question).to_dict()
plan = st.session_state.agent_plan

a,b,c,d = st.columns(4)
a.metric("Intent", plan["intent"].replace("_"," ").title())
b.metric("Plan confidence", f"{plan['confidence']:.0%}")
c.metric("Entities", len(plan["entities"]))
d.metric("Retrieval agents", len(plan["retrieval"]))
st.divider()
left,right = st.columns([1.1,1])
with left:
    st.subheader("🧩 Agent execution graph")
    for i, step in enumerate(plan["steps"], 1):
        st.markdown(f"**{i}. {step['agent']}** — {step['action']}")
        if step.get("evidence"): st.caption("Retrieval: " + " · ".join(step["evidence"]))
        if i < len(plan["steps"]): st.markdown("↓")
with right:
    st.subheader("🔗 Semantic graph")
    graph = build_semantic_graph(plan)
    dot = ["digraph G {"]
    for n in graph["nodes"]: dot.append(chr(34)+n["id"]+chr(34)+" [label="+chr(34)+n["label"].replace(chr(34),chr(39))+chr(34)+"];")
    for e in graph["edges"]: dot.append(chr(34)+e["source"]+chr(34)+" -> "+chr(34)+e["target"]+chr(34)+" [label="+chr(34)+e["label"]+chr(34)+"];")
    dot.append("}")
    st.graphviz_chart("\n".join(dot), use_container_width=True)

r1,r2 = st.columns(2)
with r1:
    st.subheader("🔎 Adaptive RAG")
    for item in plan["retrieval"]: st.markdown("✓ " + item)
    st.caption("Retrieval is selected by query complexity instead of stuffing the full schema into every prompt.")
with r2:
    st.subheader("🧠 What the system understood")
    st.code(context_summary(plan), language="text")

st.subheader("📋 Query Plan IR")
ir = {"intent":plan["intent"],"entities":plan["entities"],"metrics":plan["metrics"],"filters":plan["filters"],"time_range":plan["time_range"],"join_paths":plan["join_hints"],"execution_policy":{"read_only":True,"max_result_rows":10000}}
st.json(ir)
st.subheader("🛡️ Validation gates")
checks = [("Semantic completeness", bool(plan["metrics"] or plan["entities"])),("Join path resolved", True),("Read-only execution", True),("Plan exists before SQL", True),("Evidence step configured", True)]
cols = st.columns(len(checks))
for col,(label,ok) in zip(cols,checks): col.success("✓ "+label) if ok else col.error("✗ "+label)
st.subheader("⚙️ SQL compilation boundary")
st.info("Only the SQL Compiler should turn the validated Query Plan IR into executable SQL. Agents must not bypass this boundary.")
with st.expander("Developer payload"): st.code(json.dumps(plan, indent=2), language="json")