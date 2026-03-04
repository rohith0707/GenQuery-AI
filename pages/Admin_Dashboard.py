# pages/Admin_Dashboard.py
"""
📊 Intelligence Dashboard — Query telemetry, feedback analytics & system health.

Reads from feedback.db (via feedback_store.py).
No Snowflake connection needed — runs fully offline.
"""

import streamlit as st
import pandas as pd
import altair as alt
import time
from datetime import datetime

st.set_page_config(page_title="Intelligence Dashboard", page_icon="📊", layout="wide")

# ── Guard: redirect to landing if user hasn't entered app ─────────────────────
if "entered_app" not in st.session_state:
    st.switch_page("pages/Landing.py")

# ── Inject minimal dark-panel styling ─────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: rgba(30,41,59,0.75);
    border: 1px solid rgba(100,120,180,0.3);
    border-radius: 12px;
    padding: 1.1rem 1.4rem;
    text-align: center;
    backdrop-filter: blur(8px);
}
.metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #818cf8;
    line-height: 1.1;
}
.metric-label {
    font-size: .8rem;
    color: #94a3b8;
    margin-top: .25rem;
    letter-spacing: .5px;
    text-transform: uppercase;
}
.metric-delta-good { color: #34d399; font-size: .85rem; }
.metric-delta-warn { color: #fbbf24; font-size: .85rem; }
.section-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: #e2e8f0;
    margin: 1.6rem 0 .6rem;
    border-left: 3px solid #818cf8;
    padding-left: .6rem;
}
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
col_title, col_nav = st.columns([8, 2])
with col_title:
    st.markdown("## 📊 Intelligence Dashboard")
    st.caption("Real-time query telemetry · feedback analytics · system health")

with col_nav:
    st.markdown("<div style='margin-top:1.2rem'></div>", unsafe_allow_html=True)
    if st.button("← Back to App", use_container_width=True):
        st.switch_page("app.py")

st.divider()

# ── Auto-refresh ───────────────────────────────────────────────────────────────
_refresh_col, _spacer = st.columns([2, 8])
with _refresh_col:
    auto_refresh = st.toggle("🔄 Auto-refresh (10s)", value=False)

if auto_refresh:
    time.sleep(10)
    st.rerun()

# ── Load data ──────────────────────────────────────────────────────────────────
try:
    from feedback_store import get_stats, get_recent_feedback
    stats = get_stats()
    feedback_list = get_recent_feedback(50)
    _DATA_OK = "error" not in stats
except Exception as e:
    st.error(f"Could not read feedback.db: {e}")
    st.info("Run at least one query from the main app to populate the dashboard.")
    st.stop()

if not _DATA_OK:
    st.warning(f"Database error: {stats.get('error')}")
    st.stop()

if stats["total_queries"] == 0:
    st.info(
        "**No queries logged yet.** Head to the main app, "
        "generate a few SQL queries, and come back here to see the analytics!"
    )
    st.stop()

# ── KPI Cards ──────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Key Performance Indicators</div>",
            unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)

def _kpi(col, value, label, delta=None, delta_good=True):
    delta_html = ""
    if delta:
        cls = "metric-delta-good" if delta_good else "metric-delta-warn"
        delta_html = f"<div class='{cls}'>{delta}</div>"
    col.markdown(
        f"<div class='metric-card'>"
        f"<div class='metric-value'>{value}</div>"
        f"<div class='metric-label'>{label}</div>"
        f"{delta_html}"
        f"</div>",
        unsafe_allow_html=True
    )

_kpi(k1, stats["total_queries"],     "Total Queries")
_kpi(k2, f"{stats['avg_latency_ms']:.0f} ms",  "Avg Latency",
     delta="⚡ Fast" if stats["avg_latency_ms"] < 5000 else "🐢 Slow",
     delta_good=stats["avg_latency_ms"] < 5000)
_kpi(k3, f"{stats['cache_hit_rate_pct']}%",    "Cache Hit Rate",
     delta="✅ Efficient" if stats["cache_hit_rate_pct"] > 20 else "💡 Warming up",
     delta_good=stats["cache_hit_rate_pct"] > 20)
_kpi(k4, f"{stats['accuracy_pct']}%",          "Accuracy (Feedback)",
     delta=f"👍 {stats['thumbs_up']}  👎 {stats['thumbs_down']}",
     delta_good=stats["accuracy_pct"] >= 70)
_kpi(k5, stats["total_feedback"],              "Feedback Received")

st.markdown("<br>", unsafe_allow_html=True)

# ── Queries Over Time + Provider Breakdown ────────────────────────────────────
st.markdown("<div class='section-title'>Query Activity</div>", unsafe_allow_html=True)
ch1, ch2 = st.columns([6, 4])

with ch1:
    if stats["queries_per_day"]:
        df_daily = pd.DataFrame(stats["queries_per_day"])
        df_daily["day"] = pd.to_datetime(df_daily["day"])
        chart = (
            alt.Chart(df_daily)
            .mark_area(
                line={"color": "#818cf8", "strokeWidth": 2},
                color=alt.Gradient(
                    gradient="linear",
                    stops=[
                        alt.GradientStop(color="rgba(99,102,241,0.6)", offset=0),
                        alt.GradientStop(color="rgba(99,102,241,0.05)", offset=1),
                    ],
                    x1=1, x2=1, y1=1, y2=0,
                ),
            )
            .encode(
                x=alt.X("day:T", title="Date", axis=alt.Axis(format="%b %d")),
                y=alt.Y("count:Q", title="Queries"),
                tooltip=[alt.Tooltip("day:T", format="%Y-%m-%d"), "count:Q"],
            )
            .properties(title="Queries per Day (last 14 days)", height=220)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No daily data yet — needs queries on multiple days.")

with ch2:
    if stats["provider_breakdown"]:
        df_prov = pd.DataFrame(
            [{"provider": k, "count": v} for k, v in stats["provider_breakdown"].items()]
        ).sort_values("count", ascending=False)
        chart_prov = (
            alt.Chart(df_prov)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#818cf8")
            .encode(
                x=alt.X("count:Q", title="Queries"),
                y=alt.Y("provider:N", sort="-x", title="Provider"),
                tooltip=["provider:N", "count:Q"],
                color=alt.Color("provider:N", legend=None,
                                scale=alt.Scale(scheme="purples")),
            )
            .properties(title="Provider Usage Breakdown", height=220)
        )
        st.altair_chart(chart_prov, use_container_width=True)
    else:
        st.info("No provider data yet.")

# ── Latency Trend + Top Questions ─────────────────────────────────────────────
st.markdown("<div class='section-title'>Performance & Usage Patterns</div>",
            unsafe_allow_html=True)
ch3, ch4 = st.columns([5, 5])

with ch3:
    if stats["latency_history"]:
        df_lat = pd.DataFrame(stats["latency_history"])
        df_lat["time"] = pd.to_datetime(df_lat["ts"], unit="s")
        df_lat["idx"] = range(len(df_lat))
        chart_lat = (
            alt.Chart(df_lat)
            .mark_line(color="#34d399", strokeWidth=2)
            .encode(
                x=alt.X("idx:Q", title="Query #"),
                y=alt.Y("latency_ms:Q", title="Latency (ms)"),
                tooltip=[
                    alt.Tooltip("time:T", title="Time", format="%H:%M:%S"),
                    alt.Tooltip("latency_ms:Q", title="Latency (ms)", format=".0f"),
                ],
            )
            .properties(title="Latency Trend (last 50 queries)", height=240)
        )
        # Add average line
        avg_val = df_lat["latency_ms"].mean()
        rule = (
            alt.Chart(pd.DataFrame({"avg": [avg_val]}))
            .mark_rule(color="#fbbf24", strokeDash=[4, 4])
            .encode(y="avg:Q")
        )
        st.altair_chart(chart_lat + rule, use_container_width=True)
    else:
        st.info("No latency data yet.")

with ch4:
    if stats["top_queries"]:
        df_top = pd.DataFrame(stats["top_queries"])
        df_top["short_query"] = df_top["query"].str[:50] + "…"
        chart_top = (
            alt.Chart(df_top)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("count:Q", title="Times Asked"),
                y=alt.Y("short_query:N", sort="-x", title=""),
                color=alt.Color("count:Q", scale=alt.Scale(scheme="purpleblue"),
                                legend=None),
                tooltip=[alt.Tooltip("query:N", title="Full Query"), "count:Q"],
            )
            .properties(title="Top 10 Most Asked Questions", height=240)
        )
        st.altair_chart(chart_top, use_container_width=True)
    else:
        st.info("No query history yet.")

# ── Feedback Accuracy Timeline ────────────────────────────────────────────────
if feedback_list:
    st.markdown("<div class='section-title'>Feedback Analytics</div>",
                unsafe_allow_html=True)
    fa1, fa2 = st.columns([3, 7])

    with fa1:
        total_fb = stats["total_feedback"]
        up = stats["thumbs_up"]
        down = stats["thumbs_down"]
        if total_fb > 0:
            df_pie = pd.DataFrame({
                "type": ["👍 Correct", "👎 Incorrect"],
                "count": [up, down],
            })
            pie = (
                alt.Chart(df_pie)
                .mark_arc(innerRadius=45)
                .encode(
                    theta="count:Q",
                    color=alt.Color(
                        "type:N",
                        scale=alt.Scale(
                            domain=["👍 Correct", "👎 Incorrect"],
                            range=["#34d399", "#f87171"],
                        ),
                        legend=alt.Legend(orient="bottom"),
                    ),
                    tooltip=["type:N", "count:Q"],
                )
                .properties(title="Feedback Distribution", height=220)
            )
            st.altair_chart(pie, use_container_width=True)

    with fa2:
        df_fb = pd.DataFrame(feedback_list)
        df_fb["time"] = pd.to_datetime(df_fb["ts"], unit="s").dt.strftime("%Y-%m-%d %H:%M")
        df_fb["result"] = df_fb["rating"].map({1: "👍 Correct", -1: "👎 Incorrect"})
        df_fb["question"] = df_fb["nl_query"].str[:70] + "…"
        st.dataframe(
            df_fb[["time", "result", "question", "provider", "row_count"]].rename(columns={
                "time": "Time",
                "result": "Rating",
                "question": "Query",
                "provider": "Provider",
                "row_count": "Rows",
            }),
            use_container_width=True,
            height=220,
            hide_index=True,
        )

# ── Recent Queries Table ───────────────────────────────────────────────────────
st.markdown("<div class='section-title'>Recent Query Log</div>",
            unsafe_allow_html=True)

if stats["recent_queries"]:
    df_recent = pd.DataFrame(stats["recent_queries"])
    df_recent["time"] = pd.to_datetime(df_recent["ts"], unit="s").dt.strftime("%Y-%m-%d %H:%M:%S")
    df_recent["latency"] = df_recent["latency_ms"].apply(
        lambda x: f"{x:.0f} ms" if x else "—"
    )
    df_recent["cached"] = df_recent["cache_hit"].map({True: "✅ Yes", False: "—"})
    df_recent["question"] = df_recent["nl_query"].str[:80] + "…"

    st.dataframe(
        df_recent[["time", "question", "provider", "latency", "row_count", "cached"]].rename(
            columns={
                "time": "Time",
                "question": "Natural Language Query",
                "provider": "Provider Used",
                "latency": "Latency",
                "row_count": "Rows",
                "cached": "Cache Hit",
            }
        ),
        use_container_width=True,
        height=300,
        hide_index=True,
    )
else:
    st.info("No queries logged yet.")

# ── System Health ──────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>System Health</div>", unsafe_allow_html=True)
h1, h2, h3, h4 = st.columns(4)

# Check Ollama
with h1:
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            st.success(f"**Ollama** ✅ Running\n\n{len(models)} model(s) pulled")
        else:
            st.warning("**Ollama** ⚠️ Unexpected response")
    except Exception:
        st.error("**Ollama** ❌ Not running")

# RAG Engine
with h2:
    try:
        from rag_engine import get_rag_engine
        s = get_rag_engine().get_status()
        if s.get("initialized"):
            st.success(
                f"**RAG Engine** ✅ Ready\n\n"
                f"Tables: {s.get('schema_count', 0)} | "
                f"Cache: {s.get('cache_count', 0)}"
            )
        else:
            st.warning("**RAG Engine** ⚠️ Not initialized")
    except Exception:
        st.error("**RAG Engine** ❌ Unavailable")

# Feedback DB
with h3:
    import os
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "feedback.db")
    if os.path.exists(db_path):
        size_kb = os.path.getsize(db_path) / 1024
        st.success(f"**feedback.db** ✅ Present\n\n{size_kb:.1f} KB")
    else:
        st.info("**feedback.db** — will be created on first query")

# LLM Keys
with h4:
    from utils import get_env
    has_openai = bool(get_env("OPENAI_API_KEY"))
    has_together = bool(get_env("TOGETHER_API_KEY"))
    has_anthropic = bool(get_env("ANTHROPIC_API_KEY"))
    active = [n for n, v in [("OpenAI", has_openai), ("Together", has_together),
                               ("Anthropic", has_anthropic)] if v]
    if active:
        st.success(f"**Cloud LLMs** ✅\n\n{', '.join(active)}")
    else:
        st.warning("**Cloud LLMs** ⚠️\n\nNo API keys — using local only")

st.markdown("<br>", unsafe_allow_html=True)

# ── Actions ────────────────────────────────────────────────────────────────────
with st.expander("⚙️ Admin Actions", expanded=False):
    st.warning("⚠ These actions are irreversible.")
    if st.button("🗑️ Clear all telemetry data", type="secondary"):
        try:
            from feedback_store import clear_all
            clear_all(confirm=True)
            st.success("All data cleared.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")
