# pages/Query_Optimization.py
# Streamlit sub‑page for SQL performance optimization.
# User pastes an existing Snowflake SELECT / WITH statement; we attempt to rewrite it.
# Uses optimize_sql() from langchain_agent.py.

import streamlit as st

from langchain_agent import optimize_sql, get_generation_backend_status
from sql_validator import sanitize_sql, validate_sql_safe
from snowflake_client import get_schema_overview, run_query_with_timing
from ui.components import inject_global_styles, render_sidebar, render_header

# ---- Page Config ----
st.set_page_config(page_title="Query Optimization", page_icon="🛠", layout="wide")

# ---- Session State (shared keys defensively initialized) ----
for key, default in [
    ("dark_mode", False),
    ("auto_schema_text", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

st.session_state["current_page"] = "optimization"
st.session_state["entered_app"] = True

# ---- Styles / Palette ----
palette = inject_global_styles(st.session_state.dark_mode)
accent = palette["accent"]

# ---- Animated Background Injection (Optimization Page) ----
st.markdown(f"""
<style>
:root {{
  --opt-accent:{accent};
}}
.opt-root {{
  position:fixed;
  inset:0;
  width:100%;
  height:100vh;
  background:
    radial-gradient(circle at 26% 34%, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0) 60%),
    {palette['bg_grad']};
  overflow:hidden;
  display:flex;
  align-items:flex-start;
  justify-content:center;
  padding-top:0.9rem;
}}
.opt-particles-layer {{
  position:absolute;
  inset:0;
  pointer-events:none;
  z-index:1;
}}
.opt-inner {{
  position:relative;
  z-index:2;
  width:100%;
  max-width:1500px;
  padding:0 1.2rem 3.2rem;
}}
.opt-particle {{
  position:absolute;
  width:14px;
  height:14px;
  background:{accent};
  opacity:.35;
  border-radius:50%;
  box-shadow:0 0 12px 4px {accent}55, 0 0 28px 10px {accent}22 inset;
  animation:opt-drift 18s linear infinite;
}}
@keyframes opt-drift {{
  0% {{ transform:translateY(0) translateX(0) scale(1); opacity:.35; }}
  50% {{ transform:translateY(-60vh) translateX(25vw) scale(.55); opacity:.18; }}
  100% {{ transform:translateY(0) translateX(0) scale(1); opacity:.35; }}
}}
.opt-title {{
  font-size:clamp(1.7rem,3.2vw,2.4rem);
  font-weight:650;
  letter-spacing:.6px;
  margin:0 0 .4rem;
  background:linear-gradient(90deg,#ffffff 0%, {accent} 60%, #ffffff 100%);
  -webkit-background-clip:text;
  color:transparent;
  animation:opt-shimmer 6s linear infinite;
  filter:drop-shadow(0 4px 14px rgba(0,0,0,.35));
}}
@keyframes opt-shimmer {{
  0% {{ background-position:0% 50%; }}
  100% {{ background-position:200% 50%; }}
}}
.opt-sub {{
  font-size:.95rem;
  max-width:980px;
  line-height:1.4;
  opacity:.88;
  margin:0 0 1.2rem;
}}
.opt-reminder {{
    display:inline-block;
    padding:0.95rem 1.25rem;
    border-radius:16px;
    background:linear-gradient(135deg, rgba(15,23,42,0.94) 0%, rgba(30,58,138,0.9) 100%);
    border:1px solid {accent}66;
    box-shadow:0 14px 36px -18px rgba(15,23,42,0.85), 0 0 0 1px {accent}33 inset;
    color:#f8fafc;
    max-width:860px;
    margin:1.6rem auto 2rem;
    font-size:.96rem;
    line-height:1.55;
    letter-spacing:.24px;
    text-align:center;
}}
.dark .opt-reminder {{
    background:linear-gradient(135deg, rgba(30,41,59,0.94) 0%, rgba(22,78,99,0.9) 100%);
    border-color:{accent}aa;
    box-shadow:0 16px 42px -20px rgba(0,0,0,0.95), 0 0 0 1px {accent}55 inset;
    color:#e0f2ff;
}}
</style>
""", unsafe_allow_html=True)

def _opt_particles_html(count: int = 26) -> str:
    import random
    if "opt_particles" in st.session_state:
        return st.session_state["opt_particles"]
    random.seed(11)
    els = []
    for i in range(count):
        top = random.randint(3, 96)
        left = random.randint(1, 98)
        delay = random.uniform(0, 14)
        duration = random.uniform(16, 30)
        size = random.randint(8, 20)
        els.append(
            f"<div class='opt-particle' style='top:{top}vh;left:{left}vw;"
            f"animation-delay:{delay:.2f}s;animation-duration:{duration:.2f}s;"
            f"width:{size}px;height:{size}px;'></div>"
        )
    html = "".join(els)
    st.session_state["opt_particles"] = html
    return html

# Open animated wrapper
st.markdown(f"<div class='opt-root'><div class='opt-particles-layer'>{_opt_particles_html()}</div><div class='opt-inner'>", unsafe_allow_html=True)

# ---- Sidebar (reuse main app sidebar for consistency) ----
with st.sidebar:
    schema_hint = render_sidebar()
    # Backend capability status display removed per request.

# ---- Unified Header (navigation only; primary action lives in page body) ----
_ = render_header(
    title="🛠 Query Optimization",
    primary_label=None,
    sticky=True,
    nav=[
        {"label": "🏠 Home", "page": "pages/Landing.py"},
        {"label": "🚀 Query Generation", "page": "app.py"},
        {"label": "🛠️ Query Optimization", "page": "pages/Query_Optimization.py", "disabled": True},
    ]
)
# Page intro (moved below header for consistency)
st.caption("Paste a Snowflake SELECT / WITH query to receive a performance‑oriented rewrite.")

# (Backend capability status line removed per request)

# ---- Auto schema introspection (reuse existing overview if not present) ----
if st.session_state.auto_schema_text is None:
    try:
        st.session_state.auto_schema_text = get_schema_overview()
    except Exception as e:
        st.session_state.auto_schema_text = None
        st.caption(f"Schema introspection unavailable: {e}")

with st.expander("📘 Schema Overview (introspected)", expanded=False):
    st.code(st.session_state.auto_schema_text or "(none)", language="text")

# ---- Input Area ----
st.markdown("#### Original Query")
orig_sql = st.text_area(
    "Enter one Snowflake SELECT / WITH statement",
    height=260,
    placeholder="WITH recent_orders AS (\n    SELECT o.id, o.customer_id, o.amount, o.created_at\n    FROM orders o\n    WHERE o.created_at >= DATEADD(day,-30,CURRENT_DATE)\n)\nSELECT c.region, SUM(r.amount) AS total_amount\nFROM recent_orders r\nJOIN customers c ON c.id = r.customer_id\nGROUP BY c.region\nORDER BY total_amount DESC",
)

cols = st.columns([1,1,1,3])
opt_btn = cols[0].button("⚙️ Optimize", type="primary")
execute_btn = cols[1].button("▶️ Execute & Compare", type="secondary")
reset_btn = cols[2].button("♻️ Reset")

if reset_btn:
    st.rerun()

# ---- Action ----
if opt_btn:
    cleaned = orig_sql.strip()
    if not cleaned:
        st.error("Provide a query to optimize.")
        st.stop()

    # Basic sanitation & safety (even though user provides SQL, ensure no DDL/DML)
    sanitized = sanitize_sql(cleaned)
    ok, reason = validate_sql_safe(sanitized)
    if not ok:
        st.error(f"Rejected (unsafe / unsupported): {reason}")
        st.code(sanitized, language="sql")
        st.stop()

    with st.spinner("Optimizing query..."):
        optimized = optimize_sql(sanitized, schema_text=st.session_state.auto_schema_text or "")

    # Re-validate optimized output
    optimized_sanitized = sanitize_sql(optimized)
    ok2, reason2 = validate_sql_safe(optimized_sanitized)
    if not ok2:
        st.warning(f"Optimized version violated safety rules ({reason2}); showing original.")
        optimized_sanitized = sanitized
    
    # Store in session state for execution comparison
    if "optimized_sql" not in st.session_state:
        st.session_state.optimized_sql = None
    if "original_sql" not in st.session_state:
        st.session_state.original_sql = None
    
    st.session_state.optimized_sql = optimized_sanitized
    st.session_state.original_sql = sanitized

    # ---- Display ----
    st.markdown("### Comparison")
    cmp_cols = st.columns(2)
    with cmp_cols[0]:
        st.markdown("##### Original")
        st.code(sanitized, language="sql")
    with cmp_cols[1]:
        st.markdown("##### Optimized")
        st.code(optimized_sanitized, language="sql")

    # Metrics / Delta
    def _metrics(q: str) -> dict:
        import re
        lines = [l for l in q.splitlines() if l.strip()]
        text = q.strip()
        upper = text.upper()
        return {
            "lines": len(lines),
            "chars": len(text),
            "ctes": upper.count("WITH "),
            "joins": len(re.findall(r"\bJOIN\b", upper)),
            "select_star": bool(re.search(r"SELECT\s+\*", upper)),
            "distincts": len(re.findall(r"\bDISTINCT\b", upper)),
            "order_by": len(re.findall(r"\bORDER\s+BY\b", upper)),
            "qualify": len(re.findall(r"\bQUALIFY\b", upper)),
            "group_by": len(re.findall(r"\bGROUP\s+BY\b", upper)),
        }

    orig_m = _metrics(sanitized)
    opt_m = _metrics(optimized_sanitized)

    def _delta(a, b):  # b - a
        if isinstance(a, int) and isinstance(b, int):
            return b - a
        if isinstance(a, bool) and isinstance(b, bool):
            return (1 if b else 0) - (1 if a else 0)
        return 0

    st.markdown("#### Structural Delta")
    delta_cols = st.columns(4)
    delta_cols[0].metric("Lines", opt_m["lines"], _delta(orig_m["lines"], opt_m["lines"]))
    delta_cols[1].metric("Chars", opt_m["chars"], _delta(orig_m["chars"], opt_m["chars"]))
    delta_cols[2].metric("JOINs", opt_m["joins"], _delta(orig_m["joins"], opt_m["joins"]))
    delta_cols[3].metric("CTEs", opt_m["ctes"], _delta(orig_m["ctes"], opt_m["ctes"]))

    det_cols = st.columns(5)
    det_cols[0].metric("SELECT *", "Yes" if opt_m["select_star"] else "No",
                       ("removed" if orig_m["select_star"] and not opt_m["select_star"] else ""))
    det_cols[1].metric("DISTINCT", opt_m["distincts"], _delta(orig_m["distincts"], opt_m["distincts"]))
    det_cols[2].metric("ORDER BY", opt_m["order_by"], _delta(orig_m["order_by"], opt_m["order_by"]))
    det_cols[3].metric("GROUP BY", opt_m["group_by"], _delta(orig_m["group_by"], opt_m["group_by"]))
    det_cols[4].metric("QUALIFY", opt_m["qualify"], _delta(orig_m["qualify"], opt_m["qualify"]))

    if optimized_sanitized == sanitized:
        st.info("Heuristic or LLM produced no structural change; query may already be optimal or requires deeper statistics (cost estimates not available).")
    
    st.markdown("---")
    st.info("💡 Click **▶️ Execute & Compare** to run both queries and measure actual execution times.")

# ---- Execute & Compare Performance ----
if execute_btn:
    if "original_sql" not in st.session_state or st.session_state.original_sql is None:
        st.warning("Please optimize a query first before comparing execution times.")
        st.stop()
    
    original = st.session_state.original_sql
    optimized = st.session_state.optimized_sql
    
    st.markdown("### ⚡ Performance Comparison")
    
    # Execute both queries with timing
    perf_cols = st.columns(2)
    
    with perf_cols[0]:
        st.markdown("##### Original Query Execution")
        try:
            with st.spinner("Executing original query..."):
                orig_df, orig_time = run_query_with_timing(original)
            st.success(f"✅ Executed in **{orig_time:.3f} seconds**")
            st.caption(f"Returned {len(orig_df)} rows")
            with st.expander("View Results"):
                st.dataframe(orig_df, width="stretch")
        except Exception as e:
            st.error(f"Original query failed: {e}")
            orig_time = None
    
    with perf_cols[1]:
        st.markdown("##### Optimized Query Execution")
        try:
            with st.spinner("Executing optimized query..."):
                opt_df, opt_time = run_query_with_timing(optimized)
            st.success(f"✅ Executed in **{opt_time:.3f} seconds**")
            st.caption(f"Returned {len(opt_df)} rows")
            with st.expander("View Results"):
                st.dataframe(opt_df, width="stretch")
        except Exception as e:
            st.error(f"Optimized query failed: {e}")
            opt_time = None
    
    # Show performance metrics if both succeeded
    if orig_time is not None and opt_time is not None:
        st.markdown("---")
        st.markdown("#### 📊 Performance Metrics")
        
        time_diff = orig_time - opt_time
        time_pct = ((orig_time - opt_time) / orig_time * 100) if orig_time > 0 else 0
        
        metric_cols = st.columns(4)
        metric_cols[0].metric("Original Time", f"{orig_time:.3f}s", delta=None)
        metric_cols[1].metric("Optimized Time", f"{opt_time:.3f}s", delta=None)
        metric_cols[2].metric("Time Difference", f"{abs(time_diff):.3f}s",
                            delta=f"{time_pct:+.1f}%" if time_diff != 0 else "0%",
                            delta_color="inverse" if time_diff > 0 else "normal")
        
        if time_diff > 0:
            speedup = orig_time / opt_time if opt_time > 0 else 1
            metric_cols[3].metric("Speedup", f"{speedup:.2f}x", delta="faster")
            st.success(f"🎉 Optimized query is **{time_pct:.1f}% faster** ({time_diff:.3f}s improvement)")
        elif time_diff < 0:
            slowdown = opt_time / orig_time if orig_time > 0 else 1
            metric_cols[3].metric("Slowdown", f"{slowdown:.2f}x", delta="slower", delta_color="inverse")
            st.warning(f"⚠️ Optimized query is **{abs(time_pct):.1f}% slower** ({abs(time_diff):.3f}s slower)")
        else:
            metric_cols[3].metric("Performance", "Same", delta="0%")
            st.info("Both queries executed in similar time.")
        
        # Add visualization
        import pandas as pd
        perf_data = pd.DataFrame({
            'Query': ['Original', 'Optimized'],
            'Execution Time (s)': [orig_time, opt_time]
        })
        
        st.markdown("##### Execution Time Comparison")
        st.bar_chart(perf_data.set_index('Query'))

if not opt_btn and not execute_btn:
    st.markdown(
        f"<div class='opt-reminder'><strong>Paste a query</strong> and press "
        f"<span style='color:{accent};'>⚙️ Optimize</span> to generate an optimized version, then press "
        f"<span style='color:{accent};'>▶️ Execute &amp; Compare</span> to measure performance.</div>",
        unsafe_allow_html=True,
    )

# Remove the old "else" block that showed the info message

    # Copy to clipboard functionality using HTML/JS components
    st.markdown("#### Copy to Clipboard")
    
    # Create copy buttons with working JavaScript
    copy_cols = st.columns([1, 1, 4])
    
    # Helper to create copy button with HTML component
    def create_copy_button(label: str, sql_text: str, button_id: str, col):
        import html
        escaped_sql = html.escape(sql_text).replace('\n', '\\n').replace("'", "\\'")
        
        button_html = f"""
        <div style="margin-bottom: 0.5rem;">
            <button
                onclick="copyToClipboard_{button_id}()"
                style="
                    background: {accent};
                    color: #fff;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 13px;
                    font-weight: 600;
                    box-shadow: 0 2px 6px -2px rgba(0,0,0,0.35);
                    transition: all 0.2s;
                "
                onmouseover="this.style.opacity='0.85'"
                onmouseout="this.style.opacity='1'"
            >
                📋 {label}
            </button>
            <span id="status_{button_id}" style="
                margin-left: 10px;
                font-size: 12px;
                color: {accent};
                font-weight: 500;
            "></span>
        </div>
        <script>
            function copyToClipboard_{button_id}() {{
                const text = `{escaped_sql}`;
                
                // Create temporary textarea
                const textarea = document.createElement('textarea');
                textarea.value = text;
                textarea.style.position = 'fixed';
                textarea.style.opacity = '0';
                document.body.appendChild(textarea);
                textarea.select();
                
                try {{
                    const successful = document.execCommand('copy');
                    const statusEl = document.getElementById('status_{button_id}');
                    if (successful && statusEl) {{
                        statusEl.textContent = '✅ Copied!';
                        statusEl.style.color = '#28a745';
                        setTimeout(() => {{
                            statusEl.textContent = '';
                        }}, 2000);
                    }} else if (statusEl) {{
                        statusEl.textContent = '❌ Failed';
                        statusEl.style.color = '#dc3545';
                    }}
                }} catch (err) {{
                    console.error('Copy failed:', err);
                    const statusEl = document.getElementById('status_{button_id}');
                    if (statusEl) {{
                        statusEl.textContent = '❌ Failed';
                        statusEl.style.color = '#dc3545';
                    }}
                }}
                
                document.body.removeChild(textarea);
            }}
        </script>
        """
        col.markdown(button_html, unsafe_allow_html=True)
    
    if "original_sql" in st.session_state and st.session_state.original_sql:
        create_copy_button("Copy Original", st.session_state.original_sql, "orig", copy_cols[0])
        create_copy_button("Copy Optimized", st.session_state.optimized_sql, "opt", copy_cols[1])

# ---- Footer ----
st.markdown(
    f"<div style='text-align:center;margin-top:2.8rem;font-size:11px;color:{accent if st.session_state.dark_mode else '#395b6d'};"
    "background:rgba(255,255,255,0.55);backdrop-filter:blur(8px);padding:.55rem 1rem;border-radius:10px;'>"
    "Prototype — add governance & audit controls before productionization."
    "</div>",
    unsafe_allow_html=True
)
# Close animated wrapper
st.markdown("</div></div>", unsafe_allow_html=True)