"""Agent Workspace: inspectable agentic NL→SQL workflow."""
import json
import streamlit as st
from agentic.engine import AgenticQueryEngine

st.set_page_config(page_title="GenQuery Agent Workspace", page_icon="🧠", layout="wide")
st.title("🧠 GenQuery Agent Workspace")
st.caption("Retrieve → Resolve → Plan → Validate → Compile → Execute → Prove")

question=st.text_area("Business question",value="What was our revenue from enterprise customers in Hyderabad last quarter?",height=90)
c1,c2=st.columns([1,3])
with c1:
    analyze=st.button("▶ Analyze",type="primary",use_container_width=True)
with c2:
    st.caption("Structured artifacts and evidence are shown; private model chain-of-thought is never exposed.")

if analyze or "agent_result" not in st.session_state:
    with st.spinner("Running planner + parallel RAG + semantic validation..."):
        st.session_state.agent_result=AgenticQueryEngine().analyze(question)
r=st.session_state.agent_result
p=r.plan.to_dict()

m1,m2,m3,m4=st.columns(4)
m1.metric("Intent",p["intent"].replace("_"," ").title())
m2.metric("Confidence",f'{p["confidence"]:.0%}')
m3.metric("Entities",len(p["entities"]))
m4.metric("RAG sources",len(r.retrieval.sources))

st.divider()
left,right=st.columns([1.05,1])
with left:
    st.subheader("🧩 Agent trace")
    for i,t in enumerate(r.traces,1):
        icon="🟢" if t.status in ("completed","cache-hit") else "🔴"
        st.markdown(f"**{icon} {i}. {t.agent}** — {t.detail}")
        if t.evidence: st.caption("Evidence: "+" · ".join(t.evidence))
with right:
    st.subheader("🔗 Semantic view")
    dot=["digraph G {"]
    for e in p["entities"]: dot.append(f'"{e}" [label="{e.title()}"];')
    for m in p["metrics"]: dot.append(f'"metric:{m}" [label="{m.title()}"];')
    if p["entities"] and p["metrics"]:
        for m in p["metrics"]: dot.append(f'"{p["entities"][0]}" -> "metric:{m}" [label="measures"];')
    if len(p["entities"])>=2:
        source=p["entities"][0]; target=p["entities"][-1]
    dot.append("}")
    st.graphviz_chart("\n".join(dot),use_container_width=True)

st.subheader("🔎 Adaptive RAG")
for s in r.retrieval.sources: st.write("✓",s["source"],"—",s["detail"])

a,b=st.columns(2)
with a:
    st.subheader("📋 Query Plan IR")
    st.json(p)
with b:
    st.subheader("🛡 Validation gates")
    for k,v in r.validation.checks.items():
        (st.success if v else st.error)(("✓ " if v else "✗ ")+k)
    for e in r.validation.errors: st.error(e)
    for w in r.validation.warnings: st.warning(w)

st.subheader("⚙️ SQL Compiler")
if st.button("Compile validated plan → SQL"):
    try:
        schema=""
        try:
            from snowflake_client import get_schema_overview
            schema=get_schema_overview() or ""
        except Exception:
            pass
        with st.spinner("Compiling through the existing provider layer..."):
            st.session_state.agent_result=AgenticQueryEngine().compile(r,schema)
        r=st.session_state.agent_result
    except Exception as exc:
        st.error(str(exc))
        r=st.session_state.agent_result
if r.sql:
    st.code(r.sql,language="sql")
else:
    st.info("Compile only after semantic validation passes.")

st.subheader("🚀 Execution")
if r.sql:
    if st.button("Run SQL in Snowflake"):
        try:
            from snowflake_client import run_query,SF_PARAMS
            if not all(SF_PARAMS.get(k) for k in ("user","password","account")):
                st.warning("Snowflake credentials are not configured.")
            else:
                with st.spinner("Executing validated SQL..."):
                    df=run_query(r.sql)
                st.session_state.agent_result=r
                st.success(f"Query completed — {len(df)} rows")
                st.dataframe(df,use_container_width=True)
        except Exception as exc:
            st.error(f"Execution failed: {exc}")
            r.traces.append(type(r.traces[0])("execute","Execution Agent","failed",str(exc)))
else:
    st.info("Compile the validated plan before execution.")

st.subheader("🔐 Evidence")
if r.evidence: st.json(r.evidence)
else: st.info("Evidence is generated after compilation.")
with st.expander("Developer state"):
    st.code(json.dumps(r.to_dict(),indent=2),language="json")
