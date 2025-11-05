# design_tokens.py
# Minimal design system tokens (Simple / Clean / Neat) per DESIGN_SYSTEM.md v0.1
from __future__ import annotations
# Added explicit imports for future extensibility (e.g. dataclasses if needed).
# ---- COLOR PALETTE (LIGHT / DARK) ----
# Only essential semantic colors retained.
COLOR_PALETTE = {
    # Light theme semantic & UI color tokens.
    "light": {
        "bg": "#0A9C9EB1",
        "surface": "#FBF7F9",      # restored (was commented) to avoid KeyError in _build_palette_vars
        "surface_alt": "#ECEFF3",
        "border": "#D7DEE4",
        "text": "#1A222B",
        "subtle": "#5A6773",
        "accent": "#2563EB",
        "accent_hover": "#2E6EF5",
        "accent_active": "#1E55C4",
        # Status / feedback colors grouped for clarity.
        "success": "#15803D",
        "warning": "#B45309",      # warning color
        "error": "#B91C1C",        # error color
        "info": "#075985",         # informational color
        "focus_outline": "#2563EB",
        "code_bg": "#F4F6F9",
    },
    # Dark theme semantic & UI color tokens.
    "dark": {
        "bg": "#0F1115",
        "surface": "#1C1F24",
        "surface_alt": "#242A31",
        "border": "#2F363E",
        "text": "#F4F7FA",
        "subtle": "#A8B4C0",
        "accent": "#3B82F6",
        "accent_hover": "#5090F7",
        "accent_active": "#2A6BD6",
        "success": "#22C55E",
        "warning": "#F59E0B",
        "error": "#EF4444",
        "info": "#0EA5E9",
        "focus_outline": "#3B82F6",
        "code_bg": "#1F2430",
    },
}
# ---- PALETTE VALIDATION HELPERS (ROBUSTNESS) ----
STATUS_COLOR_KEYS = ("success", "warning", "error", "info")

def _is_valid_hex_color(value: str) -> bool:
    """
    Basic hex color validation supporting #RGB, #RRGGBB, and optional alpha (#RGBA/#RRGGBBAA).
    """
    if not isinstance(value, str) or not value.startswith("#"):
        return False
    hex_part = value[1:]
    if len(hex_part) not in (3, 4, 6, 8):
        return False
    return all(c in "0123456789ABCDEFabcdef" for c in hex_part)

def validate_color_palette(palette: dict) -> None:
    """
    Fail-fast validation:
    - Required themes exist
    - Each theme contains required status keys
    - Each hex-looking value is structurally valid
    """
    required_themes = ("light", "dark")
    for theme in required_themes:
        if theme not in palette:
            raise KeyError(f"Missing theme '{theme}' in COLOR_PALETTE")
        theme_map = palette[theme]
        for status_key in STATUS_COLOR_KEYS:
            if status_key not in theme_map:
                raise KeyError(f"Missing status color '{status_key}' in theme '{theme}'")
        for k, v in theme_map.items():
            if isinstance(v, str) and v.startswith("#") and not _is_valid_hex_color(v):
                raise ValueError(f"Invalid hex color '{v}' for key '{k}' in theme '{theme}'")

# Perform validation once at import time.
validate_color_palette(COLOR_PALETTE)

# ---- SPACING SCALE ----
# 4 / 8 rhythm subset.
SPACING_SCALE = [4, 8, 12, 16, 24, 32, 48, 64]

# ---- ELEVATION (TRIMMED) ----
ELEVATION = {
    "E0": "none",
    "E1": "0 1px 2px rgba(0,0,0,0.06)",
    "E2": "0 2px 6px rgba(0,0,0,0.10)",
}

# ---- RADII (MINIMAL) ----
RADIUS = {
    "sm": 4,
    "md": 6,
    "pill": 999,
}

# ---- TYPOGRAPHY (REDUCED SCALE) ----
TYPOGRAPHY = {
    "h1": {"size": 24, "line": 32, "weight": 600},
    "h2": {"size": 18, "line": 26, "weight": 600},
    "body": {"size": 14, "line": 20, "weight": 400},
    "body_sm": {"size": 13, "line": 18, "weight": 400},
    "mono": {"size": 13, "line": 20, "weight": 400},
    "caption": {"size": 11, "line": 16, "weight": 500},
}

# ---- MOTION (FUNCTIONAL ONLY) ----
# Added extended motion tokens for theme transitions & long background pans.
MOTION = {
    "dur_interactive": 140,  # short interactive transitions
    "dur_theme": 240,        # theme toggle duration
    "dur_long": 6000,        # long-running decorative animations
    "easing_standard": "cubic-bezier(0.4,0,0.2,1)",
    "easing_emphasis": "cubic-bezier(0.3,0,0.2,1)",
}

# ---- MINIMAL COMPONENT TOKENS ----
COMPONENT_TOKENS = {
    "button": {
        "height_md": 36,
        "padding_x_md": 16,
        "font_md": 14,
    },
    "input": {
        "height": 40,
        "padding_x": 12,
        "padding_y": 8,
        "border_width": 1,
    },
}

# ---- BREAKPOINTS (UNCHANGED FOR RESPONSIVE UTILITIES) ----
BREAKPOINTS = {
    "mobile": 640,
    "tablet": 768,
    "desktop": 1024,
    "wide": 1280,
}


def tokens_json() -> dict:
    return {
        "palette": COLOR_PALETTE,
        "spacing": SPACING_SCALE,
        "elevation": ELEVATION,
        "radius": RADIUS,
        "typography": TYPOGRAPHY,
        "motion": MOTION,
        "components": COMPONENT_TOKENS,
        "breakpoints": BREAKPOINTS,
    }


def _build_palette_vars(theme: str) -> list[str]:
    p = COLOR_PALETTE[theme]
    return [
        "--color-bg:" + p["bg"],
        "--color-surface:" + p["surface"],
        "--color-surface-alt:" + p["surface_alt"],
        "--color-border:" + p["border"],
        "--color-text:" + p["text"],
        "--color-subtle:" + p["subtle"],
        "--color-accent:" + p["accent"],
        "--color-accent-hover:" + p["accent_hover"],
        "--color-accent-active:" + p["accent_active"],
        "--color-success:" + p["success"],
        "--color-warning:" + p["warning"],
        "--color-error:" + p["error"],
        "--color-info:" + p["info"],
        "--focus-outline:" + p["focus_outline"],
        "--color-code-bg:" + p["code_bg"],
    ]


def build_css_variables(dark: bool) -> str:
    """
    Build CSS variable block for light or dark theme.
    Returns :root or [data-theme=dark] block string.
    """
    lines = _build_palette_vars("dark" if dark else "light")

    # Spacing
    for val in SPACING_SCALE:
        lines.append(f"--space-{val}:{val}px")

    # Elevation
    for k, v in ELEVATION.items():
        lines.append(f"--elevation-{k}:{v}")

    # Radius
    for k, v in RADIUS.items():
        lines.append(f"--radius-{k}:{v}px")

    # Typography
    for name, meta in TYPOGRAPHY.items():
        lines.append(f"--font-{name}-size:{meta['size']}px")
        lines.append(f"--font-{name}-line:{meta['line']}px")
        lines.append(f"--font-{name}-weight:{meta['weight']}")

    # Motion
    lines.append(f"--dur-interactive:{MOTION['dur_interactive']}ms")
    lines.append(f"--dur-theme:{MOTION['dur_theme']}ms")
    lines.append(f"--dur-long:{MOTION['dur_long']}ms")
    lines.append(f"--ease-standard:{MOTION['easing_standard']}")
    lines.append(f"--ease-emphasis:{MOTION['easing_emphasis']}")

    # Component tokens
    for comp_name, comp_tokens in COMPONENT_TOKENS.items():
        for t_name, t_val in comp_tokens.items():
            suffix = "px" if isinstance(t_val, (int, float)) else ""
            lines.append(f"--{comp_name}-{t_name.replace('_','-')}:{t_val}{suffix}")

    # Breakpoints
    for bp_name, bp_val in BREAKPOINTS.items():
        lines.append(f"--breakpoint-{bp_name}:{bp_val}px")

    selector = ":root" if not dark else "[data-theme='dark']"
    return f"{selector} {{\n  " + ";\n  ".join(lines) + ";\n}}"


def build_focus_style() -> str:
    return """
:where(button,[role='button'],input,textarea,select):focus-visible {
  outline:2px solid var(--focus-outline);
  outline-offset:2px;
  transition:outline-color 80ms var(--ease-standard);
}
"""


def build_min_motion_utilities() -> str:
    return """
.fade-in { animation:fade-in var(--dur-interactive) var(--ease-standard); }
@keyframes fade-in { from { opacity:0; } to { opacity:1; } }
@media (prefers-reduced-motion: reduce) {
  .fade-in { animation:none; }
  * { transition:none !important; }
}
"""


def build_responsive_utilities() -> str:
    return f"""
@media (max-width:{BREAKPOINTS['mobile']}px) {{
  .hide-mobile {{ display:none !important; }}
}}
"""


def build_accessibility_utilities() -> str:
    return """
.visually-hidden {
  position:absolute;
  width:1px;
  height:1px;
  padding:0;
  margin:-1px;
  overflow:hidden;
  clip:rect(0,0,0,0);
  white-space:nowrap;
  border:0;
}
"""

def build_animation_utilities() -> str:
    return """
/* Additional animation utility helpers (decorative + accessible) */
.fade-pan-bg { animation:bg-pan var(--dur-long,6000ms) linear infinite; }
@keyframes bg-pan { 0% { background-position:0% 50%; } 100% { background-position:200% 50%; } }

.anim-pulse-border { animation:pulse-border 2800ms var(--ease-emphasis,var(--ease-standard)) infinite; }
@keyframes pulse-border {
  0% { box-shadow:0 0 0 0 var(--color-accent); }
  70% { box-shadow:0 0 0 6px rgba(0,0,0,0); }
  100% { box-shadow:0 0 0 0 rgba(0,0,0,0); }
}

@media (prefers-reduced-motion: reduce) {
  .fade-pan-bg,
  .anim-pulse-border { animation:none !important; }
}
"""

def build_global_design_system_css(dark: bool) -> str:
    # Output both themes so toggling only needs data-theme attr switch.
    light_block = build_css_variables(False)
    dark_block = build_css_variables(True)
    return (
        "<style>"
        + light_block
        + "\n"
        + dark_block
        + build_focus_style()
        + build_min_motion_utilities()
        + build_animation_utilities()
        + build_responsive_utilities()
        + build_accessibility_utilities()
        + "</style>"
    )