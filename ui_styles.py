"""
ui_styles.py

Centralized styling utilities for the Streamlit SQL Agent UI.
Keeping CSS generation here keeps app.py concise and easier for both
non-technical users and developers to understand.

Usage:
    from ui_styles import build_css, build_nl2sql_title_css
    st.markdown(build_css(dark_mode=..., palette=...), unsafe_allow_html=True)
    st.markdown(build_nl2sql_title_css(accent), unsafe_allow_html=True)
"""

from typing import Dict


def build_css(dark_mode: bool, palette: Dict[str, str]) -> str:
    """
    Build the global CSS string.

    Parameters:
        dark_mode: Whether dark mode is active (affects gradients already precomputed in palette).
        palette: Dict expected keys:
            panel_bg, border_col, text_col, accent, subtle, code_bg, bg_grad

    Returns:
        A <style> block string for st.markdown.
    """
    required = ["panel_bg", "border_col", "text_col", "accent", "subtle", "code_bg", "bg_grad", "bg_solid"]
    missing = [k for k in required if k not in palette]
    if missing:
        raise ValueError(f"Palette missing required keys: {missing}")

    panel_bg = palette["panel_bg"]
    border_col = palette["border_col"]
    text_col = palette["text_col"]
    accent = palette["accent"]
    subtle = palette["subtle"]
    code_bg = palette["code_bg"]
    bg_grad = palette["bg_grad"]
    bg_solid = palette["bg_solid"]
    # Minimal CSS (hero & decorative effects removed; reduced radii/shadows/blur)
    return f"""
<style>
:root {{
  --panel-bg: var(--color-surface, {panel_bg});
  --border-col: var(--color-border, {border_col});
  --text-col: var(--color-text, {text_col});
  --accent-col: var(--color-accent, {accent});
  --subtle-col: var(--color-subtle, {subtle});
  --code-bg: var(--color-code-bg, {code_bg});
}}
* {{
  font-family: system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;
  -webkit-font-smoothing: antialiased;
}}
html, body {{
  background: {bg_grad};
  background-color: {bg_solid};
  min-height:100%;
}}
.appview-container,
.appview-container .main,
.appview-container .main .block-container,
[data-testid="stAppViewContainer"],
[data-testid="block-container"] {{
  background: transparent !important;
}}
.stApp {{
  background: {bg_grad};
  background-color: {bg_solid};
  min-height:100vh;
  color:var(--text-col);
  transition:background var(--dur-theme,240ms) var(--ease-standard,ease);
}}
h1,h2,h3,h4 {{
  font-weight:600;
  color:var(--text-col);
  margin:0.25rem 0 0.75rem;
}}
.section-box {{
  background:var(--panel-bg);
  padding:1rem 1.25rem;
  border:1px solid var(--border-col);
  border-radius:6px;
  margin-bottom:1rem;
  box-shadow:var(--elevation-E1,0 1px 2px rgba(0,0,0,0.06));
}}
/* Code blocks */
.sql-block pre,.stCode pre {{
  background:var(--code-bg)!important;
  color:var(--text-col)!important;
  font-size:13px!important;
  line-height:1.35;
  padding:0.75rem 0.9rem!important;
  border-radius:6px;
  border:1px solid var(--border-col);
  overflow-x:auto;
}}
/* Inputs */
.stTextInput input {{
  border-radius:4px;
  border:1px solid var(--border-col);
  font-size:14px;
}}
/* Buttons */
.stButton button {{
  border-radius:4px!important;
  background:var(--accent-col)!important;
  color:#fff!important;
  font-weight:500;
  font-size:14px;
  padding:0.45rem 1rem;
  border:1px solid var(--accent-col);
  transition:background 140ms var(--ease-standard,ease),filter 140ms;
}}
.stButton button:hover {{
  background:var(--color-accent-hover,{accent});
  filter:brightness(1.05);
}}
.stButton button:active {{
  background:var(--color-accent-active,{accent});
}}
.inline-hint {{
  font-size:12px;
  color:var(--subtle-col);
  margin-top:-4px;
}}
/* History items */
.history-item {{
  font-size:12px;
  padding:6px 8px;
  border-radius:4px;
  background:var(--color-surface-alt,rgba(0,0,0,0.03));
  border:1px solid var(--border-col);
  margin-bottom:6px;
  overflow-wrap:anywhere;
}}
.history-item code {{
  font-size:11px;
}}
/* Hide legacy footer */
footer {{ visibility:hidden; }}
</style>
"""


def build_nl2sql_title_css(accent: str) -> str:
    """
    Small style block for the 'Natural Language → SQL' title gradient.
    """
    return f"""
<style>
.nl2sql-title {{
  font-size:1.5rem;
  font-weight:700;
  background: linear-gradient(90deg,{accent}, #42a5f5 40%, #7dd2ff 75%, #b3e5ff 100%);
  -webkit-background-clip:text;
  color:transparent;
  letter-spacing:.6px;
  padding:4px 0 6px;
  display:inline-block;
  text-shadow: 0 1px 1px rgba(255,255,255,0.25);
}}
</style>
"""