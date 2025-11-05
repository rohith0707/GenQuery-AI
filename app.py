# app.py (refactored – delegates UI pieces to ui.components + enhanced UI system)
import streamlit as st
from utils import logger
from langchain_agent import generate_sql
from sql_validator import sanitize_sql, validate_sql_safe
from snowflake_client import run_query, get_schema_overview, run_query_with_timing  # timing added
import os
import time

from ui.components import (
    compute_palette,
    inject_global_styles,
    render_sidebar,
    render_header,
    render_query_input,
    render_sql_preview,
    render_result_tabs,
    append_history,
)

st.set_page_config(page_title="Generative SQL Intelligence", page_icon="🧪", layout="wide")

ENABLE_FILE_WATCH = os.environ.get("ENABLE_STREAMLIT_FILE_WATCH", "0").lower() in {"1", "true", "yes"}

# ---- Landing Page Redirect Logic ----
if "entered_app" not in st.session_state:
    st.switch_page("pages/Landing.py")

# ---- Auto-refresh on file changes (global .py / .css) ----
if ENABLE_FILE_WATCH:
    def _scan_watch_targets():
        root = os.path.dirname(__file__) or "."
        watch = {}
        for dirpath, dirnames, filenames in os.walk(root):
            if ".venv" in dirpath or "__pycache__" in dirpath:
                continue
            for fname in filenames:
                if fname.endswith((".py", ".css")) and not fname.startswith("." ):
                    path = os.path.join(dirpath, fname)
                    try:
                        watch[path] = os.path.getmtime(path)
                    except OSError:
                        pass
        return watch

    refresh_interval = float(os.environ.get("FILE_WATCH_INTERVAL", "2.5"))
    now = time.time()
    last_scan = st.session_state.get("_watch_scan_ts", 0.0)
    if "_watch_mod" not in st.session_state or (now - last_scan) >= refresh_interval:
        current_snapshot = _scan_watch_targets()
        previous_snapshot = st.session_state.get("_watch_mod")
        st.session_state["_watch_mod"] = current_snapshot
        st.session_state["_watch_scan_ts"] = now
        if previous_snapshot is not None:
            changed = any(
                previous_snapshot.get(p) != current_snapshot.get(p)
                for p in current_snapshot
            ) or len(current_snapshot) != len(previous_snapshot)
            if changed:
                st.session_state.pop("_header_css_injected", None)
                st.rerun()
# ---- Session State ----
if "history" not in st.session_state:
    st.session_state.history = []
if "nl_query" not in st.session_state:
    st.session_state.nl_query = ""
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
# Persist last successful SQL & DataFrame to keep charts visible after interaction reruns
if "last_sql" not in st.session_state:
    st.session_state.last_sql = None
if "last_df" not in st.session_state:
    st.session_state.last_df = None
if "auto_schema_text" not in st.session_state:
    st.session_state.auto_schema_text = None

if st.session_state.get("entered_app"):
    st.session_state["current_page"] = "app"
# ---- Styles / Palette ----
palette = inject_global_styles(st.session_state.dark_mode)
accent = palette["accent"]

# ---- Animated Background Injection (full-page) ----
# Always inject on rerun so animation persists across infinite navigation.
st.markdown(f"""
<style>
:root {{
  --landing-accent:{accent};
}}
.app-root {{
    position:relative;
    width:100%;
    min-height:100vh;
    background:
        radial-gradient(circle at 30% 30%, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0) 60%),
        {palette['bg_grad']};
    overflow-x:hidden;
    overflow-y:visible;
    display:block;
    padding:0.75rem 0 3.2rem;
}}
# .app-inner {{
#     position:relative;
#     z-index:2;
#     width:100%;
#     max-width:1450px;
#     margin:0 auto;
#     padding:0 1.2rem;
# }}
.app-hero-title {{
    font-size:clamp(1.85rem,3.4vw,2.6rem);
    font-weight:650;
    letter-spacing:.6px;
    margin:0 0 .35rem;
    background:linear-gradient(90deg,#ffffff 0%, {accent} 55%, #ffffff 100%);
    -webkit-background-clip:text;
    color:transparent;
    filter:drop-shadow(0 4px 14px rgba(0,0,0,.35));
}}
.page-sub {{
  font-size:1rem;
  max-width:980px;
  line-height:1.35;
  opacity:.88;
  margin:0 0 1.2rem;
}}
</style>
""", unsafe_allow_html=True)

# Open root wrapper without particle animation
# st.markdown("<div class='app-root'><div class='app-inner'>", unsafe_allow_html=True)

# ---- Sidebar ----
with st.sidebar:
    schema_hint = render_sidebar()
    # Backend capability status display removed per request (was OpenAI / LangChain line).

# Silent automatic schema introspection (backend-only guidance for SQL generation)
if st.session_state.auto_schema_text is None:
    try:
        st.session_state.auto_schema_text = get_schema_overview()
    except Exception:
        st.session_state.auto_schema_text = None

# ---- Header (enhanced with centered, large title) ----
st.markdown(f"""
<div style='text-align:center;margin:2rem 0 3rem 0;'>
  <h1 class='app-hero-title' style='
    font-size:clamp(2.2rem,4vw,3.5rem);
    font-weight:700;
    letter-spacing:1px;
    margin:0 0 1rem;
    color:transparent;
    filter:drop-shadow(0 4px 16px rgba(0,0,0,.4));
    '>🚀 Generative SQL Intelligence</h1>
  <p style='
    font-size:1.1rem;
    color:{palette['text_col']};
    opacity:0.85;
    margin:0 auto;
    max-width:600px;
    line-height:1.4;
  '>Transform natural language into optimized SQL queries with AI-powered intelligence</p>
</div>
""", unsafe_allow_html=True)

_ = render_header(
    title="",
    primary_label=None,
    sticky=True,
    nav=[
        {"label": "🏠 Home", "page": "pages/Landing.py"},
        {"label": "🚀 Query Generation", "page": "app.py", "disabled": True},
        {"label": "🛠️ Query Optimization", "page": "pages/Query_Optimization.py"}
    ]
)

# Query input (returns bool if Generate clicked)
run_clicked = render_query_input()

# Combine manual schema hint + auto introspected schema (if enabled) for generation
combined_schema_hint = schema_hint
if st.session_state.auto_schema_text:
    # Append with separation; LLM sees both
    combined_schema_hint = (schema_hint.strip() + "\n" + st.session_state.auto_schema_text.strip()).strip()

# ---- Action (Generate + Execute) ----
if run_clicked:
    user_q = st.session_state.nl_query.strip()
    if not user_q:
        st.error("Provide a question.")
        st.stop()

    # Generate SQL
    try:
        with st.spinner("Thinking & generating SQL..."):
            sql_raw = generate_sql(user_q, schema_text=combined_schema_hint, db_uri=None)
    except Exception as e:
        st.error(f"SQL generation failed: {e}")
        logger.exception("SQL generation error")
        st.stop()

    sql_clean = sanitize_sql(sql_raw)
    ok, reason = validate_sql_safe(sql_clean)
    if not ok:
        st.error(f"Rejected: {reason}")
        st.code(sql_clean, language="sql")
        st.stop()

    # Show immediate preview & copy
    render_sql_preview(sql_clean, accent)

    # Execute (with automatic missing-table correction / regeneration logic)
    try:
        with st.spinner("Executing on Snowflake..."):
            df, exec_time_s = run_query_with_timing(sql_clean)
    except Exception as e:
        err_msg = str(e)
        lower_msg = err_msg.lower()
        # Handle missing table/object scenarios
        if ("object not found" in lower_msg) or ("does not exist" in lower_msg):
            # Attempt direct table name substitution from suggestion
            if "Similar existing tables:" in err_msg:
                import re
                missing_match = re.search(r"'([^']+)'", err_msg)
                suggestion_match = re.search(r"Similar existing tables:\s*([A-Za-z0-9_]+)", err_msg)
                if missing_match and suggestion_match:
                    bad = missing_match.group(1)
                    good = suggestion_match.group(1)
                    if bad.lower() != good.lower():
                        fixed_sql = sql_clean.replace(bad, good)
                        st.warning(f"Retrying with corrected table name: {bad} -> {good}")
                        try:
                            with st.spinner("Retry with corrected table name..."):
                                df, exec_time_s = run_query_with_timing(fixed_sql)
                                sql_clean = fixed_sql
                        except Exception as e2:
                            st.error(f"Retry after table correction failed: {e2}")
                            logger.exception("Retry execution error")
                            st.stop()
                    else:
                        st.error(f"Query execution failed: {e}")
                        logger.exception("Execution error")
                        st.stop()
                else:
                    st.error(f"Query execution failed: {e}")
                    logger.exception("Execution error")
                    st.stop()
            else:
                # No suggestion provided; regenerate SQL with full schema hint
                try:
                    st.info("Regenerating SQL with full schema hint due to missing object...")
                    regen_sql_raw = generate_sql(user_q, schema_text=combined_schema_hint, db_uri=None)
                    regen_sql = sanitize_sql(regen_sql_raw)
                    ok2, reason2 = validate_sql_safe(regen_sql)
                    if not ok2:
                        st.error(f"Regenerated SQL rejected: {reason2}")
                        st.code(regen_sql, language="sql")
                        st.stop()
                    with st.spinner("Executing regenerated SQL..."):
                        df, exec_time_s = run_query_with_timing(regen_sql)
                        sql_clean = regen_sql
                except Exception as e3:
                    st.error(f"Query execution failed after regeneration: {e3}")
                    logger.exception("Execution error")
                    st.stop()
        else:
            st.error(f"Query execution failed: {e}")
            logger.exception("Execution error")
            st.stop()

    # Persist results in session state for subsequent reruns (chart interactions)
    st.session_state.last_sql = sql_clean
    st.session_state.last_df = df
    if 'latency_history' not in st.session_state:
        st.session_state.latency_history = []
    if 'row_history' not in st.session_state:
        st.session_state.row_history = []
    # Record metrics
    if 'exec_time_s' in locals():
        st.session_state.latency_history.append(exec_time_s * 1000.0)
    st.session_state.row_history.append(len(df))

    # Tabs for detailed exploration (reverted simple UI)
    render_result_tabs(sql_clean, df, accent)

    # History
    append_history(sql_clean, len(df))

    # Success message
    st.success(f"Query executed. Returned {len(df)} rows")
else:
    # On non-run reruns (triggered by widget interactions), re-display last results if present
    if st.session_state.last_sql is not None and st.session_state.last_df is not None:
        render_sql_preview(st.session_state.last_sql, accent)
        render_result_tabs(st.session_state.last_sql, st.session_state.last_df, accent)

# ---- Footer ----
footer_text_color = "#e2e8f0" if not st.session_state.dark_mode else accent
st.markdown(
    "<div style="
    "text-align:center;margin-top:2.8rem;font-size:11px;"
    f"color:{footer_text_color};"
    "background:rgba(15,23,42,0.55);border:1px solid rgba(148,163,184,0.25);"
    "backdrop-filter:blur(8px);padding:.55rem 1rem;border-radius:10px;'>"
    "Prototype — add governance & audit controls before productionization."
    "</div>",
    unsafe_allow_html=True
)
# Close animated wrapper
st.markdown("</div></div>", unsafe_allow_html=True)
