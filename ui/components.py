"""
ui/components.py

Reusable UI building blocks for the Streamlit Generative SQL Agent.
Goal: keep app.py lean and readable for both non‑technical users and developers.

Provided Functions:
    compute_palette(dark_mode: bool) -> dict
    render_sidebar() -> str (schema_hint)
    render_hero()
    render_query_input() -> bool  # returns True when Generate & Run clicked (button below textbox)
    render_sql_preview(sql: str, accent: str)
    render_result_tabs(sql: str, df: DataFrame, accent: str)
    append_history(sql: str, rows: int)
    render_history_sidebar()  # used inside sidebar to show history items
    render_header(title, primary_label=None, primary_kind='action', primary_url=None, sticky=True, nav=[...]) -> bool

Dependencies:
    ui_styles.build_css
    ui_styles.build_nl2sql_title_css
"""

from __future__ import annotations
import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import altair as alt
from datetime import datetime
from decimal import Decimal  # handle Decimal -> float conversion for charts
from ui_styles import build_css, build_nl2sql_title_css
from design_tokens import build_global_design_system_css


# ---------- THEME / PALETTE ----------

def compute_palette(dark_mode: bool) -> dict:
    """
    Updated palette for higher visual appeal (reduced flat white usage).
    Light: vibrant teal → azure → violet gradient with translucent frosted panels.
    Dark: deep navy → electric indigo → violet glow.
    """
    if dark_mode:
        return {
            "bg_grad": "linear-gradient(135deg,#050816 0%, #0f1e35 35%, #1e1b4b 60%, #4338ca 85%, #6d28d9 100%)",
            "bg_solid": "#050816",
            "panel_bg": "rgba(25,35,60,0.72)",
            "border_col": "rgba(120,140,200,0.25)",
            "text_col": "#eef2ff",
            "accent": "#8855ff",
            "subtle": "#94a3b8",
            "code_bg": "#0f1e35",
        }
    return {
        "bg_grad": "linear-gradient(135deg,#0ea5e9 0%, #3b82f6 35%, #6366f1 60%, #8b5cf6 85%, #d946ef 100%)",
        "bg_solid": "#09152b",
        "panel_bg": "rgba(255,255,255,0.55)",
        "border_col": "rgba(99,102,241,0.30)",
        "text_col": "#0f172a",
        "accent": "#ec4899",
        "subtle": "#475569",
        "code_bg": "#f1f5f9",
    }


# ---------- HISTORY STATE HELPERS ----------

def append_history(sql: str, rows: int):
    if "history" not in st.session_state:
        st.session_state.history = []
    st.session_state.history.append(
        {
            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
            "sql": sql,
            "rows": rows,
        }
    )


def render_history_sidebar():
    st.subheader("🕒 Recent Queries")
    hist = st.session_state.get("history", [])
    if not hist:
        st.caption("No history yet.")
        return
    for h in reversed(hist[-20:]):
        st.markdown(
            f"<div class='history-item'><strong>{h['timestamp']}</strong> • rows: {h['rows']}<br/><code>{h['sql']}</code></div>",
            unsafe_allow_html=True,
        )


# ---------- SIDEBAR + HERO + INPUT ----------

def render_sidebar() -> str:
    """
    Sidebar: Schema hint (pre-filled) + inline guidance → Recent Queries → Security → Dark mode.
    Landing / sample prompt logic removed per request.
    """
    schema_hint = st.text_area(
        "Schema hint",
        height=140,
        value=st.session_state.get(
            "schema_hint_default",
            "orders(id, customer_id, amount, created_at)\ncustomers(id, region, channel, lifetime_value)"
        ),
    )
    # Dark mode toggle (bottom)
    st.checkbox("Dark mode", key="dark_mode")

    st.markdown(
        "<div class='inline-hint'>Improves name alignment & SQL accuracy.</div>",
        unsafe_allow_html=True,
    )
    # schema_hint = st.text_area(
    #     "Schema hint",
    #     height=140,
    #     placeholder="orders(id, customer_id, amount, created_at)\ncustomers(id, region, channel, lifetime_value)",
    # )

    # History toggle
    with st.expander("🕒 Recent Queries", expanded=False):
        render_history_sidebar()

    # Security note
    with st.expander("🔐 Security", expanded=False):
        st.write(
            "- DELETE/UPDATE blocked (other analytical statements allowed)\n"
            "- Use least-privilege Snowflake role (read + metadata)\n"
            "- Prefer SHOW / DESCRIBE / EXPLAIN for diagnostics\n"
            "- Never commit secrets"
        )

    

    return schema_hint


def render_header(title: str,
                  primary_label: str | None = "➕ New Ticket",
                  primary_kind: str = "action",  # 'action' | 'link'
                  primary_url: str | None = None,
                  sticky: bool = True,
                  nav: list[dict] | None = None) -> bool:
    """
    Top application header with navigation & primary action.

    Layout:
      LEFT  : Title
      RIGHT : Navigation buttons (nav list) + optional primary action button

    Parameters:
      title          : Header title text.
      primary_label  : Label for the primary action button; if None, no primary action rendered.
      primary_kind   : 'action' (st.button) or 'link' (st.link_button) when primary_url provided.
      primary_url    : URL for link button if primary_kind='link'.
      sticky         : Apply sticky positioning CSS.
      nav            : List of navigation item dicts. Each dict may contain:
                       {
                         "label": "🛠️ Optimization",
                         "page": "pages/Query_Optimization.py",  # uses st.switch_page
                         "url": "https://...",                   # external link (ignored if page present)
                         "disabled": True | False
                       }

    Returns:
      bool -> True if primary action button clicked (only when primary_kind='action').

    Sticky Tradeoffs:
      + Keeps actions visible
      - Slight reflow on rerun
      - z-index layering needs care with other elevated containers
    """
    if sticky and not st.session_state.get("_header_css_injected"):
        st.markdown("""
        <style>
        .app-header-bar {
            position: sticky;
            top: 0;
            z-index: 100;
            padding: 0.45rem 0.9rem 0.55rem;
            background: var(--panel-bg, rgba(255,255,255,0.72));
            backdrop-filter: blur(8px);
            border-bottom: 1px solid var(--border-col, rgba(99,102,241,0.25));
            display:flex;
            align-items:center;
            justify-content:center;
            border-radius: 14px;
        }
        .dark .app-header-bar {
            background: var(--panel-bg, rgba(25,35,60,0.72));
        }
        # .app-header-title {
        #     font-size: 1.15rem;
        #     font-weight: 600;
        #     letter-spacing: .25px;
        #     margin: 0;
        #     padding-top: 2px;
        # }
        .app-header-left {
            justify-content:flex-start;
        }
        .app-header-nav-wrapper {
            background:transparent!important;
            border:none!important;
            padding:0.35rem 0.25rem;
            justify-content:center;
            gap:0.6rem;
        }
        .app-header-actions {
            background:transparent!important;
            border:none!important;
            display:flex;
            gap:0.5rem;
            justify-content:flex-end;
            align-items:center;
            flex-wrap:wrap;
        }
        .app-header-nav-wrapper .nav-btn button {
            border-radius: 999px!important;
            padding: 0.45rem 1.15rem!important;
            font-weight:600!important;
            background: rgba(15,23,42,0.08)!important;
            color: var(--text-col)!important;
            border:1px solid rgba(148,163,184,0.25)!important;
            transition:transform 180ms var(--ease-standard,ease), box-shadow 180ms, background 180ms;
        }
        .dark .app-header-nav-wrapper .nav-btn button {
            background: rgba(148,163,184,0.12)!important;
            border-color: rgba(148,163,184,0.35)!important;
            color:#e2e8f0!important;
        }
        .app-header-nav-wrapper .nav-btn button:hover {
            transform:translateY(-2px);
            box-shadow:0 10px 24px -12px rgba(15,23,42,0.45);
        }
        .app-header-actions .primary-cta button {
            border-radius: 999px!important;
            padding: 0.5rem 1.4rem!important;
            font-weight:700!important;
            letter-spacing:.4px;
            background: linear-gradient(120deg,#f97316 0%, #f97316 45%, #ef4444 100%)!important;
            border:none!important;
            color:#fff!important;
            box-shadow:0 18px 35px -18px rgba(239,68,68,0.85),0 0 0 1px rgba(255,255,255,0.08) inset;
        }
        .app-header-actions .primary-cta button:hover {
            transform:translateY(-2px) scale(1.01);
            box-shadow:0 20px 42px -18px rgba(239,68,68,0.9);
        }
        </style>
        """, unsafe_allow_html=True)
        st.session_state["_header_css_injected"] = True

    action_clicked = False
    nav_items = nav or []
    title_html = title or ""

    bar = st.container()
    with bar:
        cols = st.columns([4, 4, 4])

        # with cols[0]:
        #     st.markdown(
        #         "<div class='app-header-bar app-header-left'>"
        #         + (f"<div class='app-header-title'>{title_html}</div>" if title_html else "")
        #         + "</div>",
        #         unsafe_allow_html=True,
        #     )

        with cols[1]:
            st.markdown("<div class='app-header-bar app-header-nav-wrapper'>", unsafe_allow_html=True)
            if nav_items:
                layout = [0.3] + [1 for _ in nav_items] + [0.3]
                nav_cols = st.columns(layout)
                for index, item in enumerate(nav_items):
                    c = nav_cols[index + 1]
                    disabled = item.get("disabled", False)
                    with c:
                        st.markdown("<div class='nav-btn'>", unsafe_allow_html=True)
                        if item.get("page"):
                            if st.button(item["label"], type="secondary", disabled=disabled):
                                if not disabled:
                                    target_page = item["page"]
                                    if target_page == "pages/Landing.py" and "entered_app" in st.session_state:
                                        del st.session_state["entered_app"]
                                    if target_page == "pages/Landing.py":
                                        st.session_state["current_page"] = "landing"
                                    elif target_page == "pages/Query_Optimization.py":
                                        st.session_state["current_page"] = "optimization"
                                        st.session_state["entered_app"] = True
                                    elif target_page == "app.py":
                                        st.session_state["current_page"] = "app"
                                        st.session_state["entered_app"] = True
                                    st.switch_page(target_page)
                        elif item.get("url"):
                            st.link_button(item["label"], item["url"], type="secondary", disabled=disabled)
                        else:
                            st.button(item["label"], type="secondary", disabled=True)
                        st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='nav-placeholder'></div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with cols[2]:
            st.markdown("<div class='app-header-bar app-header-actions'>", unsafe_allow_html=True)
            if primary_label:
                st.markdown("<div class='primary-cta'>", unsafe_allow_html=True)
                if primary_kind == "link" and primary_url:
                    st.link_button(primary_label, primary_url, type="primary")
                else:
                    action_clicked = st.button(primary_label, type="primary")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='nav-placeholder'></div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    return action_clicked

def render_hero():
    # Deprecated hero retained for backward compatibility; prefer render_header().
    st.title(title if (title := "Generative SQL Intelligence") else "Generative SQL Intelligence")
    st.caption("Ask analytical questions; receive optimized secure Snowflake SQL & simple visualizations.")


def render_query_input() -> bool:
    """
    Query input area + Generate button (per latest UX requirement to place action directly under textbox).

    Returns:
      bool -> True if the '🚀 Generate & Run' button was clicked.
    """
    input_cols = st.columns([8, 4])
    run_clicked = False
    with input_cols[0]:
        st.markdown("<div class='nl2sql-title'>Natural Language → SQL</div>", unsafe_allow_html=True)
        st.text_input(
            "Your question",
            key="nl_query",
            placeholder="e.g. Monthly order count trend last 12 months",
        )
        # Primary action button placed directly below the text input
        run_clicked = st.button("🚀 Generate & Run", type="primary")
    with input_cols[1]:
        # Reserved for contextual hints / guidance (kept minimal)
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    return run_clicked


# ---------- SQL PREVIEW & COPY ----------

def _render_copy_button(button_id: str, sql: str, accent: str) -> None:
    """Render a JS-backed copy button via components to ensure clipboard access."""
    safe_sql = json.dumps(sql)
    components.html(
        f"""
        <div style='display:flex;gap:0.6rem;align-items:center;margin-top:4px;'>
            <button id='{button_id}'
                style='background:{accent};color:#fff;border:none;padding:6px 14px;
                         border-radius:8px;cursor:pointer;font-size:12px;font-weight:600;
                         letter-spacing:.4px;box-shadow:0 2px 6px -2px rgba(0,0,0,0.35);'>
                Copy SQL
            </button>
            <span id='{button_id}-status' style='font-size:12px;color:{accent};font-weight:500;'></span>
        </div>
        <script>
        const btn = document.getElementById('{button_id}');
        if (btn) {{
            btn.addEventListener('click', async () => {{
                const status = document.getElementById('{button_id}-status');
                try {{
                    await navigator.clipboard.writeText({safe_sql});
                    if (status) {{
                        status.textContent = 'Copied!';
                        setTimeout(() => {{ status.textContent = ''; }}, 1800);
                    }}
                }} catch (err) {{
                    if (status) {{
                        status.textContent = 'Copy failed';
                    }}
                }}
            }});
        }}
        </script>
        """,
        height=60,
        scrolling=False,
    )


def render_sql_preview(sql: str, accent: str):
    st.markdown("#### Generated SQL (preview)")
    st.code(sql, language="sql")
    _render_copy_button("copy-sql-preview-btn", sql, accent)


# ---------- RESULT TABS (SQL / DATA / VISUALIZATION) ----------

# ── Business Visualization helpers ────────────────────────────────────────────

def _normalize_decimals(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Convert Decimal columns to float in-place; return modified df + affected col names."""
    dec_cols: list[str] = []
    for col in df.columns:
        try:
            if df[col].apply(lambda v: isinstance(v, Decimal)).any():
                df[col] = df[col].apply(lambda v: float(v) if isinstance(v, Decimal) else v)
                dec_cols.append(col)
        except Exception:
            pass
    return df, dec_cols


def _classify_columns(df: pd.DataFrame):
    numeric = df.select_dtypes(include=["number"]).columns.tolist()
    dt_native = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()
    name_dates = [c for c in df.columns if any(k in c.lower() for k in ["date", "time", "timestamp", "_at", "_month", "_year", "_week", "_day", "_quarter"])]
    datetimes = list(dict.fromkeys(dt_native + name_dates))
    cats = [c for c in df.columns if c not in numeric and c not in datetimes]
    return numeric, datetimes, cats


def _aggregate(df: pd.DataFrame, x_col: str, y_col: str, fn: str) -> pd.DataFrame:
    ops = {
        "sum": df.groupby(x_col)[y_col].sum(),
        "mean": df.groupby(x_col)[y_col].mean(),
        "count": df.groupby(x_col)[y_col].count(),
        "max": df.groupby(x_col)[y_col].max(),
        "min": df.groupby(x_col)[y_col].min(),
    }
    return ops[fn].reset_index()


def _auto_chart_type(numeric: list, datetimes: list, cats: list, df: pd.DataFrame) -> str:
    """Pick the best default chart for business decision-making."""
    if datetimes and numeric:
        return "Time Series"
    if cats and numeric:
        n_unique = df[cats[0]].nunique() if cats else 0
        if n_unique <= 10:
            return "Pie / Donut"
        return "Horizontal Bar"
    if len(numeric) >= 2:
        return "Scatter"
    return "Bar"


def _kpi_cards(df: pd.DataFrame, numeric: list, accent: str):
    """Render a row of KPI metric cards for every numeric column (max 6)."""
    cols_to_show = numeric[:6]
    if not cols_to_show:
        st.info("No numeric columns found for KPI cards.")
        return
    card_cols = st.columns(len(cols_to_show))
    for i, col in enumerate(cols_to_show):
        total = df[col].sum()
        avg = df[col].mean()
        mx = df[col].max()
        # Growth proxy: % change from first to last value (useful for ordered data)
        pct_change = None
        if len(df) >= 2:
            first_val = df[col].iloc[0]
            last_val = df[col].iloc[-1]
            if first_val and first_val != 0:
                pct_change = ((last_val - first_val) / abs(first_val)) * 100
        with card_cols[i]:
            arrow = ""
            if pct_change is not None:
                arrow = f"<span style='color:{'#22c55e' if pct_change >= 0 else '#ef4444'};font-size:12px'>{'▲' if pct_change >= 0 else '▼'} {abs(pct_change):.1f}%</span>"
            st.markdown(
                f"""<div style='background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.3);
                border-radius:12px;padding:14px 10px;text-align:center;min-height:110px;'>
                <div style='font-size:11px;color:#94a3b8;font-weight:600;text-transform:uppercase;
                letter-spacing:1px;margin-bottom:4px;'>{col}</div>
                <div style='font-size:22px;font-weight:700;color:{accent};'>{total:,.1f}</div>
                <div style='font-size:11px;color:#94a3b8;margin-top:2px;'>
                  avg {avg:,.1f} &nbsp;|&nbsp; max {mx:,.1f}
                </div>
                <div style='margin-top:4px;'>{arrow}</div>
                </div>""",
                unsafe_allow_html=True,
            )


def _render_pie_chart(df: pd.DataFrame, cat_col: str, num_col: str, agg_fn: str):
    grouped = _aggregate(df, cat_col, num_col, agg_fn)
    grouped.columns = [cat_col, num_col]
    total = grouped[num_col].sum()
    grouped["share_%"] = (grouped[num_col] / total * 100).round(1)
    chart = (
        alt.Chart(grouped)
        .mark_arc(innerRadius=60)  # donut
        .encode(
            theta=alt.Theta(num_col, type="quantitative"),
            color=alt.Color(cat_col, legend=alt.Legend(title=cat_col), scale=alt.Scale(scheme="category20")),
            tooltip=[cat_col, alt.Tooltip(num_col, format=",.1f"), alt.Tooltip("share_%", format=".1f", title="Share %")],
        )
        .properties(height=380)
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption("🔢 Data breakdown")
    grouped_show = grouped.sort_values(num_col, ascending=False).reset_index(drop=True)
    st.dataframe(grouped_show, use_container_width=True)


def _render_horizontal_bar(df: pd.DataFrame, cat_col: str, num_col: str, agg_fn: str, sort_opt: str, top_n: int):
    grouped = _aggregate(df, cat_col, num_col, agg_fn)
    grouped.columns = [cat_col, num_col]
    if sort_opt != "none":
        grouped = grouped.sort_values(num_col, ascending=(sort_opt == "asc"))
    if top_n > 0:
        grouped = grouped.head(top_n)
    chart = (
        alt.Chart(grouped)
        .mark_bar()
        .encode(
            x=alt.X(num_col, title=f"{agg_fn.upper()}({num_col})"),
            y=alt.Y(cat_col, sort="-x", title=cat_col),
            color=alt.Color(num_col, scale=alt.Scale(scheme="purpleorange"), legend=None),
            tooltip=[cat_col, alt.Tooltip(num_col, format=",.2f")],
        )
        .properties(height=max(300, min(600, len(grouped) * 28 + 60)))
    )
    st.altair_chart(chart, use_container_width=True)


def _render_scatter(df: pd.DataFrame, x_col: str, y_col: str, color_col: str | None):
    enc = dict(
        x=alt.X(x_col, title=x_col),
        y=alt.Y(y_col, title=y_col),
        tooltip=[x_col, y_col] + ([color_col] if color_col else []),
    )
    if color_col:
        enc["color"] = alt.Color(color_col, scale=alt.Scale(scheme="category20"))
    chart = alt.Chart(df).mark_circle(size=80, opacity=0.7).encode(**enc).properties(height=420)
    # Trend line
    trend = alt.Chart(df).mark_line(color="#f59e0b", strokeDash=[4, 4]).transform_regression(x_col, y_col).encode(
        x=alt.X(x_col), y=alt.Y(y_col)
    )
    st.altair_chart((chart + trend).interactive(), use_container_width=True)


def _render_stacked_bar(df: pd.DataFrame, x_col: str, y_col: str, color_col: str, agg_fn: str):
    grouped = df.groupby([x_col, color_col])[y_col].agg(agg_fn).reset_index()
    chart = (
        alt.Chart(grouped)
        .mark_bar()
        .encode(
            x=alt.X(x_col, sort=None, title=x_col),
            y=alt.Y(y_col, stack="normalize" if agg_fn == "count" else "zero", title=f"{agg_fn.upper()}({y_col})"),
            color=alt.Color(color_col, scale=alt.Scale(scheme="category20"), legend=alt.Legend(title=color_col)),
            tooltip=[x_col, color_col, alt.Tooltip(y_col, format=",.2f")],
        )
        .properties(height=420)
    )
    st.altair_chart(chart, use_container_width=True)


def _render_time_series(df: pd.DataFrame, ts_col: str, y_col: str, agg_fn: str, color_col: str | None):
    df_ts = df.copy()
    if df_ts[ts_col].dtype.kind in ("O", "U"):
        df_ts[ts_col] = pd.to_datetime(df_ts[ts_col], errors="coerce")
    df_ts = df_ts.dropna(subset=[ts_col])
    if df_ts.empty:
        st.warning("No valid datetime values after parsing.")
        return
    df_ts["__bucket"] = df_ts[ts_col].dt.date
    if color_col and color_col != "(none)":
        grouped = df_ts.groupby(["__bucket", color_col])[y_col].agg(agg_fn).reset_index()
        grouped.columns = ["bucket", color_col, y_col]
        chart = (
            alt.Chart(grouped)
            .mark_line(point=True)
            .encode(
                x=alt.X("bucket", title=ts_col),
                y=alt.Y(y_col, title=f"{agg_fn.upper()}({y_col})"),
                color=alt.Color(color_col, scale=alt.Scale(scheme="category20")),
                tooltip=["bucket", color_col, y_col],
            )
            .properties(height=420)
        )
    else:
        grouped = _aggregate(df_ts.rename(columns={y_col: "__val"}), "__bucket", "__val", agg_fn)
        grouped.columns = ["bucket", y_col]
        base = alt.Chart(grouped).encode(x=alt.X("bucket", title=ts_col))
        line = base.mark_line(point=True, color="#8b5cf6").encode(
            y=alt.Y(y_col, title=f"{agg_fn.upper()}({y_col})"),
            tooltip=["bucket", y_col],
        )
        area = base.mark_area(opacity=0.15, color="#8b5cf6").encode(y=alt.Y(y_col))
        chart = (area + line).properties(height=420)
    st.altair_chart(chart, use_container_width=True)


def _ai_business_insight(df: pd.DataFrame, sql: str) -> str:
    """Generate a plain-English business narrative using Ollama (or fallback text)."""
    try:
        import requests as _req
        # Build a compact data sample for the prompt (max 20 rows)
        sample = df.head(20).to_string(index=False)
        stats = df.describe(include="all").to_string()
        prompt = (
            "You are a senior business analyst. Analyse the following SQL query results and write "
            "a SHORT business executive summary (3-5 bullet points max). Focus on:\n"
            "- Key findings and notable numbers\n"
            "- Top performers and laggards\n"
            "- Trends or anomalies worth attention\n"
            "- One concrete business recommendation\n\n"
            f"SQL used:\n{sql}\n\n"
            f"Data sample (first 20 rows):\n{sample}\n\n"
            f"Summary statistics:\n{stats}\n\n"
            "Write ONLY the bullet-point summary. Be specific with the actual numbers from the data."
        )
        # Try Ollama first
        _r = _req.get("http://localhost:11434/api/tags", timeout=2)
        if _r.status_code == 200:
            models = _r.json().get("models", [])
            if models:
                model_name = models[0]["name"]
                resp = _req.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 400},
                    },
                    timeout=90,
                )
                if resp.status_code == 200:
                    return resp.json().get("message", {}).get("content", "").strip()
    except Exception:
        pass
    # Statistical fallback
    numeric = df.select_dtypes(include="number").columns.tolist()
    lines = [f"📊 **Dataset:** {len(df):,} rows × {len(df.columns)} columns"]
    for col in numeric[:4]:
        lines.append(
            f"• **{col}** — Total: {df[col].sum():,.1f} | Avg: {df[col].mean():,.1f} | Max: {df[col].max():,.1f}"
        )
    return "\n".join(lines)


def render_result_tabs(sql: str, df: pd.DataFrame, accent: str):
    tabs = st.tabs(["🧪 SQL", "📊 Data", "📈 Visualization", "🎯 Business Dashboard", "🤖 AI Insights"])

    # ── Tab 0: SQL ─────────────────────────────────────────────────────────────
    with tabs[0]:
        st.markdown("##### Generated SQL")
        st.code(sql, language="sql")
        _render_copy_button("copy-sql-tab-btn", sql, accent)

    # ── Tab 1: Raw Data ────────────────────────────────────────────────────────
    with tabs[1]:
        if df.empty:
            st.info("Query executed successfully but returned no rows.")
        else:
            st.success(f"Returned {len(df)} rows.")
            st.dataframe(df, use_container_width=True)
            c1, c2 = st.columns(2)
            csv = df.to_csv(index=False).encode("utf-8")
            c1.download_button("📥 Download CSV", data=csv, file_name="query_results.csv", mime="text/csv")
            try:
                excel_buf = __import__("io").BytesIO()
                df.to_excel(excel_buf, index=False)
                c2.download_button("📥 Download Excel", data=excel_buf.getvalue(),
                                   file_name="query_results.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception:
                pass

    # ── Tab 2: Visualization ──────────────────────────────────────────────────
    with tabs[2]:
        if df.empty:
            st.info("No data to visualize.")
        else:
            df, dec_cols = _normalize_decimals(df.copy())
            numeric, datetimes, cats = _classify_columns(df)
            if dec_cols:
                st.caption(f"Normalized Decimal → float: {', '.join(dec_cols)}")

            auto = _auto_chart_type(numeric, datetimes, cats, df)
            chart_choices = ["Auto (" + auto + ")", "Bar", "Horizontal Bar", "Line", "Area",
                             "Pie / Donut", "Scatter", "Stacked Bar", "Time Series",
                             "Correlation Heatmap", "Custom Builder"]
            chart_choice = st.selectbox("Chart type", chart_choices, index=0, key="viz_chart_type")
            effective = auto if chart_choice.startswith("Auto") else chart_choice

            def _agg_controls(key_sfx=""):
                c1, c2, c3 = st.columns(3)
                agg = c1.selectbox("Aggregate", ["sum", "mean", "count", "max", "min"], index=0, key=f"agg_{key_sfx}")
                srt = c2.selectbox("Sort", ["desc", "asc", "none"], index=0, key=f"srt_{key_sfx}")
                topn = c3.number_input("Top N (0 = all)", min_value=0, max_value=500, value=0, step=5, key=f"topn_{key_sfx}")
                return agg, srt, int(topn)

            if effective == "Pie / Donut":
                if not (cats and numeric):
                    st.warning("Need a categorical + numeric column.")
                else:
                    c1, c2, c3 = st.columns(3)
                    cat_c = c1.selectbox("Category", cats, key="pie_cat")
                    num_c = c2.selectbox("Metric", numeric, key="pie_num")
                    agg_f = c3.selectbox("Aggregate", ["sum", "mean", "count"], key="pie_agg")
                    _render_pie_chart(df, cat_c, num_c, agg_f)

            elif effective == "Horizontal Bar":
                if not (cats and numeric):
                    st.warning("Need a categorical + numeric column.")
                else:
                    c1, c2 = st.columns(2)
                    cat_c = c1.selectbox("Category", cats, key="hbar_cat")
                    num_c = c2.selectbox("Metric", numeric, key="hbar_num")
                    agg_f, srt, topn = _agg_controls("hbar")
                    _render_horizontal_bar(df, cat_c, num_c, agg_f, srt, topn)

            elif effective == "Scatter":
                if len(numeric) < 2:
                    st.warning("Need at least two numeric columns.")
                else:
                    c1, c2, c3 = st.columns(3)
                    xc = c1.selectbox("X axis", numeric, index=0, key="sc_x")
                    yc = c2.selectbox("Y axis", numeric, index=min(1, len(numeric)-1), key="sc_y")
                    color_opts = ["(none)"] + cats
                    cc = c3.selectbox("Color by", color_opts, key="sc_col")
                    _render_scatter(df, xc, yc, cc if cc != "(none)" else None)

            elif effective == "Stacked Bar":
                if not (cats and numeric):
                    st.warning("Need categorical + numeric columns + a second categorical for stacking.")
                else:
                    c1, c2, c3, c4 = st.columns(4)
                    xc = c1.selectbox("X axis", cats, index=0, key="sb_x")
                    yc = c2.selectbox("Metric", numeric, index=0, key="sb_y")
                    color_opts = [c for c in cats if c != xc] or cats
                    cc = c3.selectbox("Stack by", color_opts, key="sb_col")
                    agg_f = c4.selectbox("Aggregate", ["sum", "mean", "count"], key="sb_agg")
                    _render_stacked_bar(df, xc, yc, cc, agg_f)

            elif effective == "Time Series":
                if not (datetimes and numeric):
                    st.warning("Need a datetime + numeric column.")
                else:
                    c1, c2, c3, c4 = st.columns(4)
                    ts_c = c1.selectbox("Date column", datetimes, key="ts_dt")
                    yc = c2.selectbox("Metric", numeric, key="ts_y")
                    agg_f = c3.selectbox("Aggregate", ["mean", "sum", "count"], key="ts_agg")
                    clr_opts = ["(none)"] + cats
                    clr = c4.selectbox("Color/Group by", clr_opts, key="ts_clr")
                    _render_time_series(df, ts_c, yc, agg_f, clr if clr != "(none)" else None)

            elif effective == "Correlation Heatmap":
                if len(numeric) < 2:
                    st.warning("Need ≥ 2 numeric columns.")
                else:
                    subset = st.multiselect("Columns", numeric, default=numeric[:min(6, len(numeric))], key="hm_cols")
                    if len(subset) >= 2:
                        corr_df = df[subset].corr().reset_index().melt("index")
                        corr_df.columns = ["FeatureX", "FeatureY", "Correlation"]
                        ch = (
                            alt.Chart(corr_df).mark_rect()
                            .encode(
                                x=alt.X("FeatureX", sort=None),
                                y=alt.Y("FeatureY", sort=None),
                                color=alt.Color("Correlation", scale=alt.Scale(scheme="purpleblue")),
                                tooltip=["FeatureX", "FeatureY", alt.Tooltip("Correlation", format=".2f")],
                            ).properties(height=420)
                        )
                        st.altair_chart(ch, use_container_width=True)

            elif effective in ("Bar", "Line", "Area"):
                if not (numeric and cats):
                    st.warning("Need a categorical + numeric column.")
                else:
                    c1, c2 = st.columns(2)
                    xc = c1.selectbox("Category", cats, key="bla_x")
                    yc = c2.selectbox("Metric", numeric, key="bla_y")
                    agg_f, srt, topn = _agg_controls("bla")
                    grouped = _aggregate(df.rename(columns={yc: "__val"}), xc, "__val", agg_f)
                    grouped.columns = [xc, yc]
                    if srt != "none":
                        grouped = grouped.sort_values(yc, ascending=(srt == "asc"))
                    if topn > 0:
                        grouped = grouped.head(topn)
                    mark_map = {"Bar": alt.Chart(grouped).mark_bar(),
                                "Line": alt.Chart(grouped).mark_line(point=True),
                                "Area": alt.Chart(grouped).mark_area()}
                    ch = mark_map[effective].encode(
                        x=alt.X(xc, sort=None), y=alt.Y(yc, title=f"{agg_f.upper()}({yc})"),
                        tooltip=[xc, alt.Tooltip(yc, format=",.2f")],
                    ).properties(height=420)
                    st.altair_chart(ch, use_container_width=True)

            elif effective == "Custom Builder":
                if not (numeric and (cats or datetimes)):
                    st.warning("Need numeric + categorical or datetime column.")
                else:
                    ax = cats + datetimes
                    c1, c2, c3, c4 = st.columns(4)
                    xc = c1.selectbox("X axis", ax, key="cb_x")
                    yc = c2.selectbox("Y axis", numeric, key="cb_y")
                    knd = c3.selectbox("Type", ["Bar", "Line", "Area", "Horizontal Bar"], key="cb_kind")
                    agg_f = c4.selectbox("Aggregate", ["sum", "mean", "count", "max", "min"], key="cb_agg")
                    grouped = _aggregate(df.rename(columns={yc: "__val"}), xc, "__val", agg_f)
                    grouped.columns = [xc, yc]
                    if knd == "Horizontal Bar":
                        ch = alt.Chart(grouped).mark_bar().encode(
                            x=alt.X(yc), y=alt.Y(xc, sort="-x"),
                            color=alt.Color(yc, scale=alt.Scale(scheme="purpleorange"), legend=None),
                            tooltip=[xc, alt.Tooltip(yc, format=",.2f")],
                        ).properties(height=420)
                    else:
                        mark_map = {"Bar": alt.Chart(grouped).mark_bar(),
                                    "Line": alt.Chart(grouped).mark_line(point=True),
                                    "Area": alt.Chart(grouped).mark_area()}
                        ch = mark_map[knd].encode(
                            x=alt.X(xc, sort=None), y=alt.Y(yc, title=f"{agg_f.upper()}({yc})"),
                            tooltip=[xc, alt.Tooltip(yc, format=",.2f")],
                        ).properties(height=420)
                    st.altair_chart(ch, use_container_width=True)

    # ── Tab 3: Business Dashboard ──────────────────────────────────────────────
    with tabs[3]:
        if df.empty:
            st.info("No data available.")
        else:
            df_bd, _ = _normalize_decimals(df.copy())
            numeric, datetimes, cats = _classify_columns(df_bd)

            # KPI cards row
            st.markdown("#### 📌 Key Metrics")
            _kpi_cards(df_bd, numeric, accent)
            st.markdown("---")

            # Auto best-chart
            auto_type = _auto_chart_type(numeric, datetimes, cats, df_bd)
            st.markdown(f"#### 📊 Recommended Chart — *{auto_type}*")
            try:
                if auto_type == "Time Series" and datetimes and numeric:
                    _render_time_series(df_bd, datetimes[0], numeric[0], "sum", None)
                elif auto_type == "Pie / Donut" and cats and numeric:
                    _render_pie_chart(df_bd, cats[0], numeric[0], "sum")
                elif auto_type == "Horizontal Bar" and cats and numeric:
                    _render_horizontal_bar(df_bd, cats[0], numeric[0], "sum", "desc", 15)
                elif auto_type == "Scatter" and len(numeric) >= 2:
                    _render_scatter(df_bd, numeric[0], numeric[1], cats[0] if cats else None)
                else:
                    if cats and numeric:
                        _render_horizontal_bar(df_bd, cats[0], numeric[0], "sum", "desc", 15)
                    else:
                        st.info("Add categorical or datetime columns to enable chart auto-selection.")
            except Exception as chart_err:
                st.warning(f"Auto-chart failed: {chart_err}")

            st.markdown("---")
            # Top / Bottom performers
            if cats and numeric:
                perf_col = numeric[0]
                grp_col = cats[0]
                st.markdown(f"#### 🏆 Rankings — {perf_col} by {grp_col}")
                ranked = df_bd.groupby(grp_col)[perf_col].sum().reset_index()
                ranked.columns = [grp_col, perf_col]
                ranked["Share %"] = (ranked[perf_col] / ranked[perf_col].sum() * 100).round(1)
                ranked = ranked.sort_values(perf_col, ascending=False).reset_index(drop=True)
                ranked.index += 1
                c1, c2 = st.columns(2)
                c1.markdown("**🟢 Top 10**")
                c1.dataframe(ranked.head(10), use_container_width=True)
                c2.markdown("**🔴 Bottom 10**")
                c2.dataframe(ranked.tail(10).sort_values(perf_col), use_container_width=True)

    # ── Tab 4: AI Business Insights ────────────────────────────────────────────
    with tabs[4]:
        if df.empty:
            st.info("No data available.")
        else:
            st.markdown("#### 🤖 AI-Generated Business Narrative")
            st.caption("Powered by local Ollama LLM — no data leaves your machine.")
            if st.button("✨ Generate Business Insights", key="gen_insights_btn"):
                with st.spinner("Analysing data with AI..."):
                    insight = _ai_business_insight(df, sql)
                st.markdown(
                    f"""<div style='background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.3);
                    border-radius:12px;padding:20px;line-height:1.7;font-size:15px;'>
                    {insight.replace(chr(10), "<br>")}
                    </div>""",
                    unsafe_allow_html=True,
                )
                # Download as text
                st.download_button("📥 Download Insights", data=insight,
                                   file_name="business_insights.txt", mime="text/plain")
            else:
                st.info("Click **Generate Business Insights** to get an AI narrative from your query results.")


# ---------- GLOBAL STYLE INJECTION WRAPPER ----------

def inject_global_styles(dark_mode: bool):
    """
    Inject both design token CSS variables (design_tokens.py) and legacy component styling.
    Returns palette dict for accent usage in existing code.
    """
    palette = compute_palette(dark_mode)
    # First: global design system variables + utilities (focus, elevation, motion).
    st.markdown(build_global_design_system_css(dark_mode), unsafe_allow_html=True)
    # Second: existing bespoke UI gradients / hero / specific overrides.
    st.markdown(build_css(dark_mode, palette), unsafe_allow_html=True)
    # Third: specific NL→SQL title styling using accent token.
    st.markdown(build_nl2sql_title_css(palette["accent"]), unsafe_allow_html=True)
    return palette