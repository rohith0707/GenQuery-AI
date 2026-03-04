# app.py (refactored – delegates UI pieces to ui.components + enhanced UI system)
import streamlit as st
from utils import logger
from langchain_agent import generate_sql
from sql_validator import sanitize_sql, validate_sql_safe
from snowflake_client import run_query, get_schema_overview, run_query_with_timing  # timing added
from snowflake_client import SF_PARAMS
import os
import time

try:
    from feedback_store import log_query as _log_query, record_feedback as _record_feedback
    _FEEDBACK_AVAILABLE = True
except Exception:
    _FEEDBACK_AVAILABLE = False
    def _log_query(*a, **kw): pass
    def _record_feedback(*a, **kw): pass

def _snowflake_configured() -> bool:
    """Return True only when all three required Snowflake credentials are non-empty."""
    return all(SF_PARAMS.get(k) for k in ("user", "password", "account"))

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

# RAG Engine (optional — graceful fallback if chromadb not installed)
try:
    from rag_engine import get_rag_engine, initialize_rag, TableSchema, RAG_ENABLED
    _RAG_AVAILABLE = RAG_ENABLED
except ImportError:
    _RAG_AVAILABLE = False

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
if "last_query" not in st.session_state:
    st.session_state.last_query = ""

if st.session_state.get("entered_app"):
    st.session_state["current_page"] = "app"
# ---- Feedback Helper (shared between run & re-display paths) ----
def _render_feedback_ui(sql_text: str, df, nl_q: str, rag_available: bool):
    """Render 👍/👎 feedback buttons + thank-you messages for a result."""
    _fb_key = f"fb_{abs(hash(sql_text[:80])) % 10_000_000}"
    _fb_state = st.session_state.get(_fb_key)

    if _fb_state is None:
        st.divider()
        st.caption("💬 **Was this SQL correct?** Your feedback improves future results.")
        _c1, _c2, _c3 = st.columns([1.2, 1.2, 9])
        with _c1:
            if st.button("👍  Yes", key=f"up_{_fb_key}", use_container_width=True):
                st.session_state[_fb_key] = "up"
                _record_feedback(nl_q, sql_text, rating=1,
                                 row_count=len(df) if df is not None else None)
                if rag_available:
                    try:
                        from rag_engine import get_rag_engine
                        _re = get_rag_engine()
                        if _re.is_initialized:
                            _re.cache_successful_query(nl_q, sql_text,
                                                       row_count=len(df) if df is not None else 0)
                    except Exception:
                        pass
                st.rerun()
        with _c2:
            if st.button("👎  No", key=f"dn_{_fb_key}", use_container_width=True):
                st.session_state[_fb_key] = "down"
                _record_feedback(nl_q, sql_text, rating=-1,
                                 row_count=len(df) if df is not None else None)
                # Evict from fast cache so next run gets a fresh LLM call
                try:
                    from langchain_agent import _FAST_CACHE, _OPT_CACHE, _cache_key as _ck_fn
                    _FAST_CACHE.pop(_ck_fn(nl_q, st.session_state.get("auto_schema_text", "") or ""), None)
                except Exception:
                    pass
                st.rerun()
    elif _fb_state == "up":
        st.divider()
        st.success(
            "✅ Marked **correct** — this NL→SQL pattern has been promoted to the RAG "
            "learning store. Future similar queries will be answered faster!"
        )
    else:
        st.divider()
        st.warning(
            "📝 Marked **incorrect** — cache cleared. Click **Generate SQL** again for a fresh "
            "result (will skip this cached answer and try a different approach)."
        )


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

    # ---- RAG Status ----
    if _RAG_AVAILABLE:
        try:
            _rag_status = get_rag_engine().get_status()
            if _rag_status.get("initialized"):
                with st.expander("🧠 RAG Engine", expanded=False):
                    st.caption(f"Embeddings: {_rag_status.get('embedding_mode', 'N/A')}")
                    st.caption(f"Indexed tables: {_rag_status.get('schema_count', 0)}")
                    st.caption(f"Cached queries: {_rag_status.get('cache_count', 0)}")
                    st.caption(f"Few-shot examples: {_rag_status.get('few_shot_count', 0)}")
                    st.caption(f"Conversation turns: {_rag_status.get('conversation_turns', 0)}")
        except Exception:
            pass

    # ---- LLM Provider Status ----
    try:
        from langchain_agent import get_generation_backend_status, OLLAMA_BASE_URL, LMSTUDIO_BASE_URL
        _bs = get_generation_backend_status()
        def _picon(ok): return "✅" if ok else "❌"
        with st.expander("⚡ LLM Providers", expanded=False):
            st.caption("**Paid / Cloud (needs API key)**")
            st.caption(f"{_picon(_bs.get('openai_available'))} OpenAI")
            st.caption(f"{_picon(_bs.get('anthropic_available'))} Anthropic")
            st.caption(f"{_picon(_bs.get('gemini_available'))} Gemini")
            st.caption(f"{_picon(_bs.get('llama_available'))} LLaMA (HF/Groq key)")
            st.caption(f"{_picon(_bs.get('together_available'))} Together AI (free credits)")
            st.caption("**Free & Local (no key needed)**")
            _ollama_err = _bs.get('ollama_error') or ''
            _ollama_ok = 'connection refused' not in _ollama_err
            _lm_err = _bs.get('lmstudio_error') or ''
            _lm_ok = 'connection refused' not in _lm_err
            st.caption(f"{'🟢' if _ollama_ok else '🔴'} Ollama ({OLLAMA_BASE_URL})")
            st.caption(f"{'🟢' if _lm_ok else '🔴'} LM Studio ({LMSTUDIO_BASE_URL})")
            if not any([_bs.get('openai_available'), _bs.get('anthropic_available'),
                        _bs.get('gemini_available'), _bs.get('together_available'),
                        _ollama_ok, _lm_ok]):
                st.warning("No LLM available! Add a key to .env or start Ollama/LM Studio.")
                st.markdown(
                    "**Quick free options:**\n"
                    "1. [Download Ollama](https://ollama.com) → `ollama pull codellama`\n"
                    "2. [LM Studio](https://lmstudio.ai) → load a model\n"
                    "3. [Together AI](https://together.ai) → free $25 credits → add `TOGETHER_API_KEY` to `.env`"
                )
    except Exception:
        pass

# Silent automatic schema introspection (backend-only guidance for SQL generation)
if st.session_state.auto_schema_text is None:
    try:
        st.session_state.auto_schema_text = get_schema_overview()
    except Exception:
        st.session_state.auto_schema_text = None

# ---- RAG Initialization (index schema into vector store) ----
if _RAG_AVAILABLE and "rag_initialized" not in st.session_state:
    try:
        from snowflake_client import get_rich_schema_for_rag
        _rag_engine = initialize_rag()
        if _rag_engine.is_initialized:
            _raw_tables = get_rich_schema_for_rag()
            if _raw_tables:
                _rag_tables = [
                    TableSchema(
                        table_name=t["table_name"],
                        columns=t["columns"],
                        database=t.get("database", ""),
                        schema=t.get("schema", ""),
                    )
                    for t in _raw_tables
                ]
                _rag_engine.index_schema(_rag_tables)
                logger.info("RAG: Indexed %d tables from Snowflake schema", len(_rag_tables))
        st.session_state.rag_initialized = True
    except Exception as _rag_err:
        logger.warning("RAG initialization failed: %s", _rag_err)
        st.session_state.rag_initialized = False

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
        {"label": "🛠️ Query Optimization", "page": "pages/Query_Optimization.py"},
        {"label": "📊 Dashboard", "page": "pages/Admin_Dashboard.py"},
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

    # Generate SQL (streaming for Ollama real-time display; fallback for all other providers)
    sql_raw = None
    _s_hdr = st.empty()
    _s_disp = st.empty()
    try:
        from langchain_agent import generate_sql_stream as _gss
        _s_hdr.markdown(
            f"<p style='color:{accent};font-weight:600;font-size:.95rem;margin:0 0 .25rem;'>"
            "⚡ Generating SQL in real-time…</p>",
            unsafe_allow_html=True,
        )
        _toks: list = []
        for _tok in _gss(user_q, schema_text=combined_schema_hint):
            _toks.append(_tok)
            _s_disp.code("".join(_toks), language="sql")
        _s_hdr.empty()
        _s_disp.empty()
        if _toks:
            _joined = "".join(_toks)
            # Only accept if output actually contains SQL keywords
            if any(kw in _joined.lower() for kw in ("select", "with", "show", "describe")):
                sql_raw = _joined
    except Exception:
        _s_hdr.empty()
        _s_disp.empty()

    try:
        if not sql_raw:
            with st.spinner("Thinking & generating SQL…"):
                sql_raw = generate_sql(user_q, schema_text=combined_schema_hint, db_uri=None)
    except Exception as e:
        err_str = str(e)
        st.error(f"SQL generation failed: {err_str}")
        logger.exception("SQL generation error")
        # Show actionable free-LLM help when no key is configured
        if "OPENAI_API_KEY missing" in err_str or "All provider attempts failed" in err_str:
            st.info(
                "**No LLM API key found.** You can use a completely free local LLM:\n\n"
                "**Option 1 — Ollama (easiest, fully local):**\n"
                "1. Download from [ollama.com](https://ollama.com) and install\n"
                "2. Run: `ollama pull codellama` (or `ollama pull llama3`)\n"
                "3. Ollama starts automatically — re-run your query\n\n"
                "**Option 2 — LM Studio (GUI-based):**\n"
                "1. Download from [lmstudio.ai](https://lmstudio.ai)\n"
                "2. Load any model, enable the local server\n"
                "3. Re-run your query\n\n"
                "**Option 3 — Together AI (free $25 credits):**\n"
                "1. Sign up at [together.ai](https://together.ai) (free)\n"
                "2. Copy your API key to `.env` as `TOGETHER_API_KEY=your_key`\n"
                "3. Restart the app"
            )
        st.stop()

    sql_clean = sanitize_sql(sql_raw)
    ok, reason = validate_sql_safe(sql_clean)
    if not ok:
        st.error(f"Rejected: {reason}")
        st.code(sql_clean, language="sql")
        st.stop()

    # Show immediate preview & copy
    render_sql_preview(sql_clean, accent)

    # ---- Demo mode: Snowflake not configured — show SQL only ----
    if not _snowflake_configured():
        st.warning(
            "**Demo Mode** — SQL generated successfully but Snowflake is not connected. "
            "Fill in your credentials in the `.env` file to execute queries."
        )
        st.info(
            "**How to connect Snowflake** — edit `.env` in the project root:\n\n"
            "```env\n"
            "SNOWFLAKE_USER=your_username\n"
            "SNOWFLAKE_PASSWORD=your_password\n"
            "SNOWFLAKE_ACCOUNT=orgname-accountlocator   # e.g. myorg-xy12345\n"
            "SNOWFLAKE_WAREHOUSE=COMPUTE_WH\n"
            "SNOWFLAKE_DATABASE=MY_DATABASE\n"
            "SNOWFLAKE_SCHEMA=PUBLIC\n"
            "SNOWFLAKE_ROLE=ACCOUNTADMIN\n"
            "```\n\n"
            "Save the file and **restart the app** (`streamlit run app.py`)."
        )
        # Still cache the generated SQL in RAG for future use
        if _RAG_AVAILABLE:
            try:
                _rag_eng = get_rag_engine()
                if _rag_eng.is_initialized:
                    _rag_eng.add_conversation_turn(user_q, sql_clean)
            except Exception:
                pass
        st.stop()

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
            err_str = str(e)
            st.error(f"Query execution failed: {err_str}")
            if "Missing required Snowflake environment variables" in err_str or "snowflake" in err_str.lower():
                st.info(
                    "**Snowflake credentials missing.** Edit `.env` in the project root:\n\n"
                    "```env\n"
                    "SNOWFLAKE_USER=your_username\n"
                    "SNOWFLAKE_PASSWORD=your_password\n"
                    "SNOWFLAKE_ACCOUNT=orgname-accountlocator\n"
                    "SNOWFLAKE_WAREHOUSE=COMPUTE_WH\n"
                    "SNOWFLAKE_DATABASE=MY_DATABASE\n"
                    "SNOWFLAKE_SCHEMA=PUBLIC\n"
                    "```\n\nThen restart with `streamlit run app.py`."
                )
            logger.exception("Execution error")
            st.stop()

    # Persist results in session state for subsequent reruns (chart interactions)
    st.session_state.last_sql = sql_clean
    st.session_state.last_df = df
    st.session_state.last_query = user_q
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

    # ———— Feedback UI (👍 / 👎) ———————————————————————————————————————
    _render_feedback_ui(sql_clean, df, user_q, _RAG_AVAILABLE)

    # History
    append_history(sql_clean, len(df))

    # ———— Query telemetry logging —————————————————————————————————————
    try:
        from langchain_agent import get_last_used_provider
        _provider = get_last_used_provider() or "unknown"
        try:
            _lat_ms = exec_time_s * 1000.0  # defined after successful run_query_with_timing
        except NameError:
            _lat_ms = None
        _log_query(user_q, sql_clean, provider=_provider,
                   latency_ms=_lat_ms, row_count=len(df))
    except Exception:
        pass

    # ---- RAG: Cache successful query + track conversation ----
    if _RAG_AVAILABLE:
        try:
            _rag_eng = get_rag_engine()
            if _rag_eng.is_initialized:
                _rag_eng.cache_successful_query(
                    question=user_q, sql=sql_clean, row_count=len(df)
                )
                _rag_eng.add_conversation_turn(user_q, sql_clean)
        except Exception:
            pass

    # Success message
    st.success(f"Query executed. Returned {len(df)} rows")
else:
    # On non-run reruns (triggered by widget interactions), re-display last results if present
    if st.session_state.last_sql is not None and st.session_state.last_df is not None:
        render_sql_preview(st.session_state.last_sql, accent)
        render_result_tabs(st.session_state.last_sql, st.session_state.last_df, accent)
        _render_feedback_ui(
            st.session_state.last_sql,
            st.session_state.last_df,
            st.session_state.get("last_query", ""),
            _RAG_AVAILABLE,
        )

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
