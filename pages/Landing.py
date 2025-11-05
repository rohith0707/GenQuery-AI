# pages/Landing.py
"""
Landing page with AI animated theme and navigation buttons.

Provides:
  - Animated gradient / particles background via CSS keyframes
  - Intro hero with brief description
  - Two primary navigation buttons:
        Query Generation  -> app.py
        Query Optimization -> pages/Query_Optimization.py
"""

import streamlit as st
from ui.components import compute_palette

# ---- Page Config ----
st.set_page_config(page_title="AI SQL Assistant Landing", page_icon="🤖", layout="wide")

# ---- Styles / Palette ----
dark_mode = st.session_state.get("dark_mode", False)
palette = compute_palette(dark_mode)
accent = palette["accent"]
# Track landing context
st.session_state["entered_app"] = False
st.session_state["current_page"] = "landing"
# Skipping global design token injection on landing page (custom isolated styling).

# ---- Custom Animated Background / Theme ----
# Always inject landing CSS (no gating) so animation persists on every visit.
st.markdown(f"""
<style>
:root {{
  --text-col: {palette['text_col']};
  --bg-grad: {palette['bg_grad']};
  --accent: {accent};
}}
/* Animated gradient backdrop */
.landing-root {{
    position: fixed;
    inset: 0;
    width: 100%;
    height: 100vh;
    background: 
        radial-gradient(circle at 20% 20%, rgba(99, 102, 241, 0.15) 0%, rgba(99, 102, 241, 0) 50%),
        radial-gradient(circle at 80% 80%, rgba(168, 85, 247, 0.15) 0%, rgba(168, 85, 247, 0) 50%),
        radial-gradient(circle at 40% 60%, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0) 50%),
        var(--bg-grad);
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.particles-layer {{
    position: absolute;
    inset: 0;
    pointer-events: none;
    overflow: hidden;
    z-index: 1;
}}
.landing-inner {{
    position: relative;
    z-index: 2;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 2.2rem 2.2rem 2.8rem;
    max-width: 1080px;
    margin: 0 auto;
    text-align: center;
}}
/* Floating particle dots */
.particle {{
    position: absolute;
    width: 14px;
    height: 14px;
    background: {accent};
    opacity: 0.35;
    border-radius: 50%;
    box-shadow: 0 0 12px 4px {accent}55, 0 0 28px 10px {accent}22 inset;
    animation: drift 14s linear infinite;
}}
@keyframes drift {{
    0% {{ transform: translateY(0) translateX(0) scale(1); opacity:.35; }}
    50% {{ transform: translateY(-60vh) translateX(20vw) scale(0.6); opacity:.15; }}
    100% {{ transform: translateY(0) translateX(0) scale(1); opacity:.35; }}
}}
/* Title shimmer */
.landing-title {{
    font-size: clamp(2.8rem, 5vw, 4.2rem);
    font-weight: 800;
    line-height: 1.05;
    background: linear-gradient(90deg, #ffffff 0%, {accent} 40%, #ffffff 80%);
    background-size: 200% 100%;
    -webkit-background-clip: text;
    color: transparent;
    animation: shimmer 4s linear infinite;
    letter-spacing: 1.2px;
    filter: drop-shadow(0 6px 20px rgba(0,0,0,0.5));
    margin-bottom: 1.2rem;
    text-align: center;
}}
@keyframes shimmer {{
    0% {{ background-position: 0% 50%; }}
    100% {{ background-position: 200% 50%; }}
}}
.landing-sub {{
    font-size: 1.2rem;
    max-width: 900px;
    color: var(--text-col);
    opacity: 0.92;
    margin-bottom: 3rem;
    line-height: 1.5;
    text-align: center;
    font-weight: 400;
    letter-spacing: 0.3px;
}}
#landing-top-nav {{
  width: 100%;
  max-width: 1100px;
  margin: 0 auto 2.2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 1.2rem;
}}
#landing-top-nav .brand-badge {{
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.55rem 0.95rem;
  border-radius: 999px;
  background: rgba(15,23,42,0.35);
  color: #f8fafc;
  letter-spacing: 0.6px;
  font-weight: 600;
  font-size: 0.92rem;
  box-shadow: 0 14px 28px -18px rgba(15,23,42,0.75);
}}
.dark #landing-top-nav .brand-badge {{
  background: rgba(148,163,184,0.22);
  color: #e2e8f0;
}}
#landing-top-nav .nav-group {{
  display: flex;
  align-items: center;
  gap: 0.8rem;
  flex-wrap: wrap;
}}
#landing-top-nav .nav-group .nav-btn button {{
  border-radius: 999px!important;
  padding: 0.4rem 1.1rem!important;
  font-weight: 600!important;
  background: rgba(15,23,42,0.08)!important;
  color: var(--text-col)!important;
  border: 1px solid rgba(148,163,184,0.25)!important;
  transition: transform .18s var(--ease-standard,ease), box-shadow .18s;
}}
.dark #landing-top-nav .nav-group .nav-btn button {{
  background: rgba(148,163,184,0.18)!important;
  border-color: rgba(148,163,184,0.35)!important;
  color: #e2e8f0!important;
}}
#landing-top-nav .nav-group .nav-btn button:hover {{
  transform: translateY(-2px);
  box-shadow: 0 12px 26px -16px rgba(15,23,42,0.55);
}}
#landing-top-nav .nav-group .primary-cta button {{
  border-radius: 999px!important;
  padding: 0.48rem 1.35rem!important;
  font-weight: 700!important;
  letter-spacing: .4px;
  background: linear-gradient(120deg,#f97316 0%, #f97316 45%, #ef4444 100%)!important;
  border: none!important;
  color: #fff!important;
  box-shadow: 0 18px 36px -18px rgba(239,68,68,0.85), 0 0 0 1px rgba(255,255,255,0.08) inset;
}}
#landing-top-nav .nav-group .primary-cta button:hover {{
  transform: translateY(-2px) scale(1.01);
  box-shadow: 0 20px 42px -18px rgba(239,68,68,0.9);
}}
.nav-buttons {{
    display: flex;
    gap: 1.2rem;
    flex-wrap: wrap;
    margin-bottom: 2.6rem;
}}
.nav-buttons button, .nav-buttons a {{
    font-size: 1rem !important;
    font-weight: 600 !important;
    letter-spacing: .4px;
    padding: 0.85rem 1.55rem !important;
    border-radius: 12px !important;
    box-shadow: 0 4px 16px -4px rgba(0,0,0,0.35), 0 0 0 1px {accent}55 inset;
    transition: transform .25s, box-shadow .25s, background .25s;
}}
.nav-buttons button:hover {{
    transform: translateY(-3px);
    box-shadow: 0 8px 20px -4px rgba(0,0,0,0.45), 0 0 0 1px {accent}88 inset;
}}
.visual-gallery {{
  width: 100%;
  max-width: 1100px;
  margin: 1.5rem auto 3.2rem;
  display: grid;
  gap: 1.6rem;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}}
.gallery-card {{
  position: relative;
  border-radius: 26px;
  padding: 1.6rem 1.8rem;
  background: linear-gradient(140deg, rgba(255,255,255,0.68) 0%, rgba(255,255,255,0.32) 100%);
  border: 1px solid rgba(255,255,255,0.4);
  backdrop-filter: blur(18px);
  box-shadow: 0 16px 36px -18px rgba(15,23,42,0.55);
  text-align: left;
}}
.dark .gallery-card {{
  background: linear-gradient(140deg, rgba(30,41,59,0.78) 0%, rgba(30,41,59,0.45) 100%);
  border-color: rgba(148,163,184,0.25);
}}
.gallery-card svg {{
  width: 100%;
  height: auto;
  margin-bottom: 1.1rem;
}}
.gallery-card h4 {{
  margin: 0 0 0.45rem;
  font-size: 1.05rem;
  color: var(--text-col);
}}
.gallery-card p {{
  font-size: 0.9rem;
  line-height: 1.45;
  color: var(--text-col);
  opacity: 0.88;
}}
.footer-note {{
    font-size: 11px;
    margin-top: 3.8rem;
    opacity: 0.85;
    width: 100%;
    padding: 0.65rem 1.2rem;
    background: linear-gradient(90deg, rgba(255,255,255,0.65) 0%, rgba(255,255,255,0.40) 100%);
    backdrop-filter: blur(10px);
    border-top: 1px solid {accent}33;
    letter-spacing: .5px;
    display: flex;
    justify-content: center;
    align-items: center;
    box-shadow: 0 -4px 12px -6px rgba(0,0,0,0.35), 0 0 0 1px {accent}22 inset;
}}
.dark .footer-note {{
    background: linear-gradient(90deg, rgba(25,35,60,0.72) 0%, rgba(25,35,60,0.55) 100%);
    border-top: 1px solid {accent}55;
    box-shadow: 0 -4px 14px -6px rgba(0,0,0,0.65), 0 0 0 1px {accent}44 inset;
}}
/* Responsive container */
.hero-overlay {{
    position: relative;
    margin: 0 auto 2.4rem;
    padding: 1.6rem 2.2rem 1.9rem;
    max-width: 960px;
    background: linear-gradient(135deg, rgba(255,255,255,0.60) 0%, rgba(255,255,255,0.30) 100%);
    backdrop-filter: blur(14px);
    border: 1px solid {accent}44;
    border-radius: 24px;
    box-shadow: 0 8px 28px -8px rgba(0,0,0,0.40), 0 0 0 1px {accent}22 inset;
    animation: heroPulse 6s ease-in-out infinite;
}}
.dark .hero-overlay {{
    background: linear-gradient(135deg, rgba(25,35,60,0.72) 0%, rgba(25,35,60,0.45) 100%);
    border-color: {accent}55;
}}
@keyframes heroPulse {{
    0% {{ box-shadow: 0 8px 28px -8px rgba(0,0,0,0.40), 0 0 0 1px {accent}22 inset; }}
    50% {{ box-shadow: 0 10px 36px -10px rgba(0,0,0,0.55), 0 0 0 1px {accent}55 inset; }}
    100% {{ box-shadow: 0 8px 28px -8px rgba(0,0,0,0.40), 0 0 0 1px {accent}22 inset; }}
}}
</style>
""", unsafe_allow_html=True)

# Inject floating particles (simple deterministic set)
def _particles_html(count: int = 24) -> str:
    import random
    # Use a stable seed only first time; persist HTML in session state.
    if "landing_particles" in st.session_state:
        return st.session_state["landing_particles"]
    random.seed(42)
    els = []
    for i in range(count):
        top = random.randint(4, 96)
        left = random.randint(2, 98)
        delay = random.uniform(0, 10)
        duration = random.uniform(14, 26)
        size = random.randint(8, 20)
        els.append(
            f"<div class='particle' style='top:{top}vh;left:{left}vw;"
            f"animation-delay:{delay:.2f}s;animation-duration:{duration:.2f}s;"
            f"width:{size}px;height:{size}px;'></div>"
        )
    html = "".join(els)
    st.session_state["landing_particles"] = html
    return html

# Initialize animated background root + persistent particles + inner wrapper
# Structure:
# <div.landing-root>
#    <div.particles-layer>...particles...</div>
#    <div.landing-inner>  ...content... </div>
# </div>
st.markdown(
    f"<div class='landing-root fade-pan-bg'><div class='particles-layer'>{_particles_html()}</div><div class='landing-inner'>",
    unsafe_allow_html=True,
)


# ---- Top Navigation ----
with st.container():
  st.markdown("<div id='landing-top-nav'>", unsafe_allow_html=True)
  brand_col, actions_col = st.columns([2.2, 1.8])
  # with brand_col:
  #   st.markdown(
  #     "<div class='brand-badge'>✨ AI Data Copilot</div>",
  #     unsafe_allow_html=True,
  #   )
  with actions_col:
    st.markdown("<div class='nav-group'>", unsafe_allow_html=True)
    top_btn_cols = st.columns(2)
    with top_btn_cols[0]:
      st.markdown("<div class='nav-btn primary-cta'>", unsafe_allow_html=True)
      gen_top = st.button("🚀 Query Generation", key="landing_gen_top", type="primary")
      st.markdown("</div>", unsafe_allow_html=True)
    with top_btn_cols[1]:
      st.markdown("<div class='nav-btn'>", unsafe_allow_html=True)
      opt_top = st.button("🛠 Query Optimization", key="landing_opt_top", type="secondary")
      st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
  st.markdown("</div>", unsafe_allow_html=True)

# Handle top navigation clicks
if "gen_top" in locals() and gen_top:
  st.session_state["entered_app"] = True
  st.session_state["current_page"] = "app"
  st.switch_page("app.py")

if "opt_top" in locals() and opt_top:
  st.session_state["entered_app"] = True
  st.session_state["current_page"] = "optimization"
  st.switch_page("pages/Query_Optimization.py")


# ---- Hero Section + Animated Imagery ----
st.markdown("""
<div class='landing-title'>🚀 Generative SQL Intelligence</div>
<div class='landing-sub'>Transform natural language into secure, optimized Snowflake SQL queries. Explore intelligent query generation, advanced performance tuning, and intuitive visual analytics with our AI-powered assistant.</div>
""", unsafe_allow_html=True)

# Animated SVG Illustrations (AI brain + data flow)
animated_svg = f"""
<div style='display:flex;justify-content:center;gap:3.2rem;flex-wrap:wrap;margin-bottom:2.8rem;'>
  <svg width='220' height='220' viewBox='0 0 220 220' style='filter:drop-shadow(0 6px 14px rgba(0,0,0,0.35));'>
    <defs>
      <radialGradient id='gradBrain' fx='35%' fy='35%'>
        <stop offset='0%' stop-color='{accent}' stop-opacity='1'/>
        <stop offset='60%' stop-color='{accent}' stop-opacity='0.35'/>
        <stop offset='100%' stop-color='{accent}' stop-opacity='0'/>
      </radialGradient>
    </defs>
    <circle cx='110' cy='110' r='94' fill='url(#gradBrain)' opacity='0.55'>
      <animate attributeName='r' values='86;94;86' dur='6s' repeatCount='indefinite'/>
    </circle>
    <g stroke='{accent}' stroke-width='2' fill='none' stroke-linecap='round' opacity='0.9'>
      <path d='M70 130 C55 110 60 80 90 70 C90 45 130 45 130 70 C160 75 165 110 150 130 C155 155 125 170 110 160 C95 170 65 155 70 130 Z'>
        <animate attributeName='stroke-dasharray' values='4 8;8 4;4 8' dur='5s' repeatCount='indefinite'/>
      </path>
      <circle cx='100' cy='95' r='5'>
        <animate attributeName='r' values='4;7;4' dur='3.2s' repeatCount='indefinite'/>
      </circle>
      <circle cx='125' cy='95' r='5'>
        <animate attributeName='r' values='7;4;7' dur='3.2s' repeatCount='indefinite'/>
      </circle>
      <path d='M100 95 Q110 108 125 95'>
        <animate attributeName='stroke-width' values='2;4;2' dur='4s' repeatCount='indefinite'/>
      </path>
      <path d='M110 110 C120 120 120 135 110 145 C100 135 100 120 110 110 Z'>
        <animate attributeName='stroke-dashoffset' values='0;24;0' dur='6s' repeatCount='indefinite'/>
      </path>
    </g>
  </svg>

  <svg width='220' height='220' viewBox='0 0 220 220' style='filter:drop-shadow(0 6px 14px rgba(0,0,0,0.35));'>
    <defs>
      <linearGradient id='gradFlow' x1='0%' y1='0%' x2='100%' y2='100%'>
        <stop offset='0%' stop-color='{accent}' stop-opacity='0.9'/>
        <stop offset='100%' stop-color='{accent}' stop-opacity='0.2'/>
      </linearGradient>
    </defs>
    <rect x='35' y='35' width='150' height='150' rx='18' fill='none' stroke='{accent}' stroke-width='2' opacity='0.65'/>
    <g stroke='url(#gradFlow)' stroke-width='2' fill='none' stroke-linecap='round'>
      <path d='M55 75 H165'>
        <animate attributeName='stroke-dasharray' values='0 140;70 70;0 140' dur='5.5s' repeatCount='indefinite'/>
      </path>
      <path d='M55 110 H165'>
        <animate attributeName='stroke-dasharray' values='70 70;0 140;70 70' dur='5.5s' repeatCount='indefinite'/>
      </path>
      <path d='M55 145 H165'>
        <animate attributeName='stroke-dasharray' values='0 140;70 70;0 140' dur='5.5s' repeatCount='indefinite'/>
      </path>
      <circle cx='110' cy='75' r='6' fill='{accent}'>
        <animate attributeName='cx' values='55;165;55' dur='9s' repeatCount='indefinite'/>
      </circle>
      <circle cx='110' cy='145' r='6' fill='{accent}'>
        <animate attributeName='cx' values='165;55;165' dur='9s' repeatCount='indefinite'/>
      </circle>
    </g>
    <text x='110' y='110' text-anchor='middle' fill='{accent}' font-size='16' font-weight='600' opacity='0.85'>
      DATA FLOW
      <animate attributeName='opacity' values='0.35;0.85;0.35' dur='4.4s' repeatCount='indefinite'/>
    </text>
  </svg>
</div>
"""
st.markdown(animated_svg, unsafe_allow_html=True)

# Additional visual gallery (concept art)
gallery_html = f"""
<div class='visual-gallery'>
  <div class='gallery-card'>
    <svg viewBox='0 0 260 160' xmlns='http://www.w3.org/2000/svg'>
      <defs>
        <linearGradient id='galleryGrad1' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='{accent}' stop-opacity='0.85'/>
          <stop offset='100%' stop-color='{accent}' stop-opacity='0.25'/>
        </linearGradient>
      </defs>
      <rect x='16' y='22' width='228' height='116' rx='18' fill='url(#galleryGrad1)' opacity='0.75'/>
      <g stroke='#ffffff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' opacity='0.9'>
        <path d='M48 108 L96 64 L140 88 L188 46' fill='none'/>
        <circle cx='48' cy='108' r='5' fill='#ffffff'/>
        <circle cx='96' cy='64' r='5' fill='#ffffff'/>
        <circle cx='140' cy='88' r='5' fill='#ffffff'/>
        <circle cx='188' cy='46' r='5' fill='#ffffff'/>
      </g>
      <text x='30' y='46' fill='#ffffff' font-size='13' font-weight='600'>AI decision graph</text>
    </svg>
    <h4>AI Orchestrated Workflows</h4>
    <p>Watch intent, schema context, and guardrails converge into a single guidance surface for analysts.</p>
  </div>
  <div class='gallery-card'>
    <svg viewBox='0 0 260 160' xmlns='http://www.w3.org/2000/svg'>
      <rect x='20' y='28' width='220' height='104' rx='18' fill='rgba(15,23,42,0.15)' />
      <g fill='{accent}'>
        <rect x='40' y='96' width='28' height='24' rx='6' opacity='0.85'/>
        <rect x='80' y='64' width='28' height='56' rx='6' opacity='0.75'/>
        <rect x='120' y='80' width='28' height='40' rx='6' opacity='0.65'/>
        <rect x='160' y='52' width='28' height='68' rx='6' opacity='0.9'/>
        <rect x='200' y='72' width='28' height='48' rx='6' opacity='0.7'/>
      </g>
      <text x='40' y='56' fill='#ffffff' font-size='13' font-weight='600'>Optimization impact</text>
    </svg>
    <h4>Before & After Benchmarking</h4>
    <p>Instantly compare execution paths to highlight cost savings, speedups, and data freshness.</p>
  </div>
  <div class='gallery-card'>
    <svg viewBox='0 0 260 160' xmlns='http://www.w3.org/2000/svg'>
      <rect x='18' y='24' width='224' height='112' rx='18' fill='rgba(255,255,255,0.6)' />
      <path d='M38 112 Q78 72 118 92 T198 68' stroke='{accent}' stroke-width='4' fill='none' opacity='0.85'/>
      <circle cx='118' cy='92' r='6' fill='{accent}' />
      <circle cx='198' cy='68' r='6' fill='{accent}' />
      <circle cx='78' cy='72' r='6' fill='{accent}' />
      <text x='38' y='54' fill='rgba(15,23,42,0.78)' font-size='13' font-weight='600'>Story-driven dashboards</text>
    </svg>
    <h4>Visual Narrative Snapshots</h4>
    <p>Serve curated dashboards that narrate the why behind query results, not just the numbers.</p>
  </div>
</div>
"""
st.markdown(gallery_html, unsafe_allow_html=True)

# ---- Feature Highlights ----
st.markdown("### Why This Assistant?")
feat_cols = st.columns(3)
feat_cols[0].markdown(
    f"""
    <div style='padding:1rem 1rem 0.8rem;border:1px solid {accent}33;
                border-radius:14px;background:rgba(255,255,255,0.55);backdrop-filter:blur(10px);'>
      <h4 style='margin-top:0;'>Context‑Aware</h4>
      <p style='font-size:0.85rem;line-height:1.3;'>Schema introspection + natural language parsing produce aligned, secure SQL.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
feat_cols[1].markdown(
    f"""
    <div style='padding:1rem 1rem 0.8rem;border:1px solid {accent}33;
                border-radius:14px;background:rgba(255,255,255,0.55);backdrop-filter:blur(10px);'>
      <h4 style='margin-top:0;'>Performance Focus</h4>
      <p style='font-size:0.85rem;line-height:1.3;'>Optimization engine rewrites queries emphasizing efficiency & clarity.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
feat_cols[2].markdown(
    f"""
    <div style='padding:1rem 1rem 0.8rem;border:1px solid {accent}33;
                border-radius:14px;background:rgba(255,255,255,0.55);backdrop-filter:blur(10px);'>
      <h4 style='margin-top:0;'>Visual Insight</h4>
      <p style='font-size:0.85rem;line-height:1.3;'>Instant charts & metrics help validate results and explore data trends.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- Footer ----
st.markdown(
    f"<div class='footer-note' style='color:{accent if st.session_state.get('dark_mode') else '#394f6d'};'>"
    "Prototype — add governance & audit controls before productionization."
    "</div>",
    unsafe_allow_html=True,
)

st.markdown("</div></div>", unsafe_allow_html=True)