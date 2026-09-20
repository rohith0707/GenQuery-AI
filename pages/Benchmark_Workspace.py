"""Benchmark Workspace: repeatable, inspectable evaluation of GenQuery."""
import json,os
from pathlib import Path
import streamlit as st
from benchmark.runner import load_cases,run,summary

st.set_page_config(page_title="GenQuery Benchmarks",page_icon="📈",layout="wide")
st.title("📈 GenQuery Live Benchmarks")
st.caption("Measure retrieval, planning, validation, SQL compilation and execution.")

limit=st.slider("Golden questions",1,20,10)
live=st.checkbox("Live Snowflake execution",value=False,help="Use only a read-only benchmark environment.")
if live and os.getenv("GENQUERY_BENCHMARK_LIVE")!="1":
    st.warning("Live execution requires GENQUERY_BENCHMARK_LIVE=1.")
if st.button("▶ Run Benchmark",type="primary"):
    if live and os.getenv("GENQUERY_BENCHMARK_LIVE")!="1":
        st.error("Refusing live execution without explicit safety flag.")
    else:
        with st.spinner("Running benchmark cases..."):
            rows=run(load_cases(Path("benchmark/datasets/golden.jsonl"),limit),live)
        st.session_state["benchmark_report"]={"summary":summary(rows),"results":[r.__dict__ for r in rows]}
report=st.session_state.get("benchmark_report")
if report:
    s=report["summary"]
    a,b,c,d=st.columns(4)
    a.metric("End-to-end pass",f'{s["pass_rate"]:.1f}%')
    b.metric("Metric accuracy",f'{s["metric_accuracy"]:.1f}%')
    c.metric("Plan validity",f'{s["plan_validity"]:.1f}%')
    d.metric("SQL compile",f'{s["sql_compile_rate"]:.1f}%')
    e,f,g=st.columns(3)
    e.metric("Execution accuracy",f'{s["execution_accuracy"]:.1f}%')
    f.metric("Validation",f'{s["validation_pass_rate"]:.1f}%')
    g.metric("P50 latency",f'{s["latency_p50_ms"]:.0f} ms')
    st.subheader("Case-level results")
    st.dataframe(report["results"],use_container_width=True)
    st.download_button("Download benchmark report",json.dumps(report,indent=2),"benchmark-report.json","application/json")
else:
    st.info("Run the benchmark to generate a measurable report.")
