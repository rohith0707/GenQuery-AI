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

def render_result_tabs(sql: str, df: pd.DataFrame, accent: str):
    tabs = st.tabs(["🧪 SQL", "📊 Data", "📈 Visualization"])
    with tabs[0]:
        st.markdown("##### Generated SQL")
        st.code(sql, language="sql")
        _render_copy_button("copy-sql-tab-btn", sql, accent)

    with tabs[1]:
        if df.empty:
            st.info("Query executed successfully but returned no rows.")
        else:
            st.success(f"Returned {len(df)} rows.")
            st.dataframe(df, width="stretch")
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download CSV", data=csv, file_name="query_results.csv", mime="text/csv")

    with tabs[2]:
        if df.empty:
            st.info("No data to visualize.")
            return

        # Column classification (+ Decimal normalization)
        # Convert any Decimal-valued columns to float to avoid Altair type inference warnings
        dec_columns = []
        for col in df.columns:
            try:
                if df[col].apply(lambda v: isinstance(v, Decimal)).any():
                    df[col] = df[col].apply(lambda v: float(v) if isinstance(v, Decimal) else v)
                    dec_columns.append(col)
            except Exception:
                pass

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        datetime_cols_native = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()
        name_based_dates = [c for c in df.columns if any(k in c.lower() for k in ["date", "time", "timestamp", "_at"])]
        datetime_cols = list(dict.fromkeys(datetime_cols_native + name_based_dates))
        cat_cols = [c for c in df.columns if c not in numeric_cols and c not in datetime_cols]
        if dec_columns:
            st.caption(f"Normalized Decimal columns to float: {', '.join(dec_columns)}")

        st.markdown("##### 📊 Select a chart type")
        chart_choice = st.selectbox(
            "Chart type",
            [
                "None",
                "Bar",
                "Line",
                "Area",
                "Time Series",
                "Correlation Heatmap",
                "Custom Builder",
            ],
            index=1 if (numeric_cols and (cat_cols or datetime_cols)) else 0,
        )

        if chart_choice == "None":
            st.info("Choose a chart type to visualize results.")
            return

        def aggregate(df_local, x_col, y_col, fn):
            ops = {
                "sum": df_local.groupby(x_col)[y_col].sum().reset_index(),
                "mean": df_local.groupby(x_col)[y_col].mean().reset_index(),
                "count": df_local.groupby(x_col)[y_col].count().reset_index(),
            }
            return ops[fn]

        # Time Series
        if chart_choice == "Time Series":
            if not (datetime_cols and numeric_cols):
                st.warning("Requires at least one datetime and one numeric column.")
                return
            ts_col = st.selectbox("Datetime column", datetime_cols, index=0)
            y_col = st.selectbox("Numeric column", numeric_cols, index=0)
            agg_fn = st.selectbox("Aggregate", ["mean", "sum"], index=0)
            df_ts = df.copy()
            if df_ts[ts_col].dtype.kind in ("O", "U"):
                df_ts[ts_col] = pd.to_datetime(df_ts[ts_col], errors="coerce")
            df_ts = df_ts.dropna(subset=[ts_col])
            if df_ts.empty:
                st.warning("No valid datetime values after parsing.")
                return
            df_ts["__bucket"] = df_ts[ts_col].dt.date if hasattr(df_ts[ts_col], "dt") else df_ts[ts_col]
            grouped = aggregate(df_ts.rename(columns={y_col: "__val"}), "__bucket", "__val", agg_fn)
            grouped.columns = ["bucket", y_col]
            chart = (
                alt.Chart(grouped)
                .mark_line(point=True)
                .encode(
                    x=alt.X("bucket", title=ts_col),
                    y=alt.Y(y_col, title=f"{agg_fn.upper()}({y_col})"),
                    tooltip=["bucket", y_col],
                )
                .properties(height=420)
            )
            st.altair_chart(chart, use_container_width=True)
            return

        # Correlation Heatmap
        if chart_choice == "Correlation Heatmap":
            if len(numeric_cols) < 2:
                st.warning("Need at least two numeric columns.")
                return
            subset = st.multiselect("Numeric columns", numeric_cols, default=numeric_cols[: min(5, len(numeric_cols))])
            if len(subset) < 2:
                st.info("Select two or more columns.")
                return
            corr_df = df[subset].corr().reset_index().melt("index")
            corr_df.columns = ["FeatureX", "FeatureY", "Correlation"]
            chart = (
                alt.Chart(corr_df)
                .mark_rect()
                .encode(
                    x=alt.X("FeatureX", sort=None),
                    y=alt.Y("FeatureY", sort=None),
                    color=alt.Color("Correlation", scale=alt.Scale(scheme="purpleblue"), legend=alt.Legend(title="ρ")),
                    tooltip=["FeatureX", "FeatureY", alt.Tooltip("Correlation", format=".2f")],
                )
                .properties(height=420)
            )
            st.altair_chart(chart, use_container_width=True)
            return

        # Simple aggregated charts (Bar / Line / Area) with immediate output + optional data preview
        if chart_choice in ("Bar", "Line", "Area"):
            if not (numeric_cols and cat_cols):
                st.warning("Need at least one categorical and one numeric column.")
                return

            sel_cols = st.columns(5)
            x_col = sel_cols[0].selectbox("Categorical", cat_cols, index=0)
            y_col = sel_cols[1].selectbox("Numeric", numeric_cols, index=0)
            agg_fn = sel_cols[2].selectbox("Aggregate", ["sum", "mean", "count"], index=0)
            sort_opt = sel_cols[3].selectbox("Sort", ["desc", "asc", "none"], index=0)
            show_data = sel_cols[4].checkbox("Show aggregated data", value=True)

            grouped = aggregate(df.rename(columns={y_col: "__val"}), x_col, "__val", agg_fn)
            grouped.columns = [x_col, y_col]

            if sort_opt != "none":
                grouped = grouped.sort_values(by=y_col, ascending=(sort_opt == "asc"))

            mark_map = {"Bar": "bar", "Line": "line", "Area": "area"}
            mark = mark_map[chart_choice]
            if mark == "bar":
                chart = alt.Chart(grouped).mark_bar()
            elif mark == "line":
                chart = alt.Chart(grouped).mark_line(point=True)
            else:
                chart = alt.Chart(grouped).mark_area()

            st.markdown("###### Chart Output")
            chart = chart.encode(
                x=alt.X(x_col, sort=None, title=x_col),
                y=alt.Y(y_col, title=f"{agg_fn.upper()}({y_col})"),
                tooltip=[x_col, y_col],
            ).properties(height=420, width=880)
            st.altair_chart(chart, use_container_width=True)

            if show_data:
                st.caption("Aggregated data used for chart")
                st.dataframe(grouped, width="stretch")

            return

        # Custom Builder
        if chart_choice == "Custom Builder":
            if not (numeric_cols and (cat_cols or datetime_cols)):
                st.warning("Need at least one numeric plus one categorical or datetime column.")
                return
            axis_choices = cat_cols + datetime_cols
            x = st.selectbox("X (categorical/time)", axis_choices, index=0)
            y = st.selectbox("Y (numeric)", numeric_cols, index=0)
            chart_kind = st.selectbox("Type", ["Bar", "Line", "Area"], index=0)
            agg_fn = st.selectbox("Aggregate", ["sum", "mean", "count"], index=0)
            sort_opt = st.selectbox("Sort", ["desc", "asc", "none"], index=0)
            grouped = aggregate(df.rename(columns={y: "__val"}), x, "__val", agg_fn)
            grouped.columns = [x, y]
            if sort_opt != "none":
                grouped = grouped.sort_values(by=y, ascending=(sort_opt == "asc"))
            mark_map = {"Bar": "bar", "Line": "line", "Area": "area"}
            mark = mark_map[chart_kind]
            if mark == "bar":
                chart = alt.Chart(grouped).mark_bar()
            elif mark == "line":
                chart = alt.Chart(grouped).mark_line(point=True)
            else:
                chart = alt.Chart(grouped).mark_area()
            chart = chart.encode(
                x=alt.X(x, sort=None, title=x),
                y=alt.Y(y, title=f"{agg_fn.upper()}({y})"),
                tooltip=[x, y],
            ).properties(height=420, width=880)
            st.altair_chart(chart, use_container_width=True)
            return


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