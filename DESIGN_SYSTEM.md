# Figma Design Specification – Data-Centric Web Application
## Pages Structure
Cover, Styles (Design System), Components, Landing, Query Optimization, Prototypes.
## Design Principles
Clarity, performance insight emphasis, trust signals, minimal aesthetic, restrained accent usage for CTAs and key metrics.
## Design Tokens
### Color Palette (WCAG AA contrast targets)
Primary/50 #eef2ff
Primary/100 #e0e7ff
Primary/300 #93c5fd
Primary/500 #3b82f6
Primary/600 #2563eb
Primary/700 #1d4ed8
Neutral/0 #ffffff
Neutral/50 #f9fafb
Neutral/100 #f3f4f6
Neutral/200 #e5e7eb
Neutral/300 #d1d5db
Neutral/400 #9ca3af
Neutral/500 #6b7280
Neutral/600 #4b5563
Neutral/700 #374151
Neutral/800 #1f2937
Neutral/900 #111827
Success/500 #10b981
Warning/500 #f59e0b
Error/500 #ef4444
Info/500 #0ea5e9
Accent use: Primary/500 for primary CTAs, Success/500 for positive metrics, Warning/Error for anomalies; keep accent usage <10% surface area.
Elevation levels: E0 none, E1 0 1px 2px rgba(0,0,0,0.06), E2 0 2px 4px rgba(0,0,0,0.10), E3 0 4px 12px rgba(0,0,0,0.14), E4 0 8px 24px rgba(0,0,0,0.18).
Borders: 1px Neutral/200 light theme, 1px Neutral/700 dark theme at 24% opacity.
### Typography Scale
Display 48/56 SemiBold
H1 40/48 SemiBold
H2 32/40 SemiBold
H3 28/36 SemiBold
H4 24/32 Medium
H5 20/28 Medium
H6 18/26 Medium
Body/Large 18/28 Regular
Body/Default 16/24 Regular
Body/Small 14/20 Regular
Caption 12/16 Regular
Mono Code 13/20 Regular (JetBrains Mono or Fira Code)
Use fluid clamp for Body/Default: clamp(15px, 1.1vw, 16px).
### Spacing Scale (px)
2 4 8 12 16 20 24 32 40 48 64 80 96.
Grid gutters: mobile 16, tablet 24, desktop 32.
### Grid System
Mobile 4 columns (min 72px each, 16px gutter).
Tablet 8 columns.
Desktop 12 columns (max content width 1280px).
Use AutoLayout with hug and fixed constraints; annotate constraints in Components page.
### Iconography
Icon sizes: 16 small, 20 default, 24 medium, 32 feature, 48 hero decorative.
Export-ready SVG with 2px stroke, rounded joins.
### Motion Guidelines
Duration: interactive 150–250ms ease-out; entrance 240–320ms ease; data viz load stagger ≤600ms total; toast slide-in 180ms.
Easing: standard cubic-bezier(0.4,0,0.2,1); emphasize cubic-bezier(0.3,0,0.2,1).
Reduce motion preference: swap to opacity + scale(0.98) transitions only.
### Focus States
2px outline Primary/500 outside border + 2px offset; high-contrast mode uses #000 or #fff depending on surface.
### Accessibility Notes
Color contrast AA for text ≥4.5:1 regular, 3:1 large; verify Primary/500 on Neutral/50, Neutral/0 text on Primary/600.
All interactive elements have role and aria-label; tooltips describe non-text icons.
### Component Tokens
Radius: xs 4, sm 6, md 8, lg 12, xl 20, pill full.
Shadows reference elevation levels; interactive lift adds E1 → E2 on hover.
## Components (Variants & States)
Buttons: primary (filled Primary/500, hover 600, active 700), secondary (outline Primary/500 bg transparent hover bg Primary/50), tertiary (text Neutral/600 hover Neutral/800 underline subtle).
Disabled: 40% opacity + cursor not-allowed.
Sizes: sm 28h, md 36h, lg 44h (horizontal padding 16/20/24).
States: default, hover, active, focus, loading (spinner left), disabled.
Dropdown: variants single-select, multi-select; size md, lg; states closed, open, error.
SegmentedControl: min 3 options; active segment bold + accent bottom bar 3px.
Tags: variants neutral, success, warning, error, selected (accent background 8%).
Badges: small count (red), status (success/warning/error), with pulse animation for live metrics (600ms loop opacity).
Tooltips: 8px radius, E3 elevation, appear after 300ms hover delay.
Modals: width 560 default, 840 large; header H4, body scroll area; close icon at 24px.
Toasts: position bottom-right; statuses Queued (Neutral/400), Running (Info/500 animated progress), Completed (Success/500), Failed (Error/500).
## Landing Page Layout
Navigation bar: height 72 desktop, 64 mobile; left logo, center links, right dark/light toggle and Sign Up CTA.
Hero: 2-column desktop (text left 7 columns, visual right 5), stacked mobile; background animated subtle radial data particles (opacity 8%, motion reduced -> static gradient).
Value proposition: H2 + supporting Body/Default; primary CTA Sign Up, secondary CTA View Docs.
Feature grid: 3 columns desktop (or 4?), choose 3x2 layout; each card md radius, icon 32, H5 title, Body/Small descriptor.
Performance comparison interactive: slider or toggle showing before vs after metrics (latency, cost); animate numbers count-up 240ms.
Customer trust signals: row of grayscale logos (max height 40) + testimonial carousel (auto advance 6s, manual controls).
Pricing teaser: brief copy + 3 plan preview cards (Starter, Growth, Enterprise) with button View Full Plans.
Footer: 4 column desktop (Product, Company, Resources, Legal) + social icons row + compliance badges (SOC2, GDPR) + copyright line.
Mobile: stack sections, collapse grid to 1 column, navigation uses hamburger with slide panel.
## Query Optimization Page Layout
Global header: breadcrumb (Environment / Database) + filter bar (Environment dropdown, Database dropdown, Time Range segmented: 1h 24h 7d 30d Custom).
Sidebar (280px desktop, overlay mobile): collapsible groups Saved Queries, Templates, History, Performance Insights; each group has chevron toggle, count badge.
Main workspace split: top row Query Editor (fills left 60%) and Execution Plan Visualizer (right 40%), bottom row Performance Metrics Panel (left 50%) and Recommendations Panel (right 50%).
Query Editor: monospace font, line numbers, inline lint warning badges (yellow tag), error badges (red).
Tabs above editor: Raw SQL, Visual Builder, Version Diff (show diff view with added/removed lines color-coded green/red).
Execution Plan Visualizer: node graph; each node shows operator name, row estimate, cost badge (cost color scale: low Neutral/300, medium Warning/500, high Error/500).
Performance Metrics Panel: cards for latency, CPU %, I/O bytes, rows scanned, cache hit rate; sparkline mini chart (60x24) in each card.
Recommendations Panel: list items ranked; item contains title, impact tag (High/Medium/Low colored), estimated improvement %, code snippet (mono).
Inline comparison original vs optimized: side-by-side diff plus delta metrics summary bar (e.g., -32% latency, -41% rows scanned).
Export buttons group: JSON, CSV, PDF; Share link generator copies URL with query hash.
Status bar persistent bottom: last run duration, resource consumption summary, environment indicator green/yellow/red.
Empty states: use illustration placeholder (optional) + microcopy guiding next action.
Error states: card with icon, message, retry button primary; logs link secondary.
Toast flow: Queued -> Running progress bar -> Completed success or Failed error.
## Component Library Coverage
Provide Figma components with variants for light/dark, size (sm/md/lg), state (default/hover/active/focus/disabled/loading), and semantic (success/warning/error).
Editor component variant includes showLineNumbers, showDiff, theme (light/dark).
Node component variant: size (compact/expanded), state (selected/hover).
Recommendation item variant: impact (High/Medium/Low), expanded details toggle.
## Annotations
Each component frame includes autolayout parameters (direction, gap, padding), constraints (e.g., left + top, center stretch), and naming following PascalCase.
Use comments for interaction: e.g., Button/Primary/Hover opacity 96% + elevation E2.
## Prototyping Flows
Flow 1: Landing → Sign Up modal → After confirm → Query Optimization Page with sample query loaded.
Flow 2: Query run → Toast sequence → Recommendations update.
Link hotspots on CTAs; include back navigation from Query Optimization to Landing (logo click).
## Accessibility Documentation
Provide table listing component roles, ARIA attributes, keyboard interactions (Space/Enter activate button, Esc closes modal).
Focus order: Nav → Hero CTA → Feature cards → Comparison interactive → Pricing teaser → Footer links.
Editor shortcuts list: Ctrl+Enter run query, Ctrl+F find, Alt+Arrow cycle tabs.
## Interaction States Reference
Buttons: document pixel change on press (translateY 1px), color shift -5% luminance.
Dropdown: open animation scaleY 0.92→1 + fade 0–100% 180ms.
Tooltip: fade + slight translateY -4→0.
Toast: slide from translateY 12 to 0, fade 0→100%.
## Handoff Notes
Include export of SVG icons in /icons with naming kebab-case (e.g., performance-gauge.svg).
Provide spacing guidelines sheet with example component redlines (padding values).
Map tokens to CSS variables: --color-primary-500, --space-16, --radius-md, etc.
Reference existing code functions: [render_sidebar()](ui/components.py:89), [render_query_input()](ui/components.py:152), [render_sql_preview()](ui/components.py:200) for eventual integration alignment.
## Dark Mode Adjustments
Background Neutral/900, cards Neutral/800, text Neutral/50, reduce shadow spread (E3 -> E2) to soften contrast.
Charts use dark grid lines rgba(255,255,255,0.08), axis labels Neutral/200.
## Documentation Page Content
Include sections: Color, Typography, Spacing, Grid, Elevation, Icons, Motion, Accessibility, Components Index.
Provide token JSON snippet for devs.
## Token JSON Example
{
  "color": {"primary":{"500":"#3b82f6"}, "neutral":{"700":"#374151"}, "success":{"500":"#10b981"}},
  "space":[2,4,8,12,16,20,24,32,40,48,64,80,96],
  "radius":{"sm":6,"md":8,"lg":12,"xl":20},
  "elevation":{"E1":"0 1px 2px rgba(0,0,0,0.06)"}
}
## Developer Notes
Use CSS clamp, prefers-reduced-motion media query, and data-theme attribute for light/dark switching.
Components map to design tokens; no ad-hoc colors.
## QA Checklist
Contrast passes, keyboard navigation complete, modals trap focus, toast announcements use aria-live polite.
## Open Questions
Authentication flows (placeholder), multi-environment deep link spec, versioning strategy for saved queries.
## Next Steps
Build Figma components first, then wire prototypes; validate contrast; export icon set; review with accessibility audit.
## Version
v1.0 design spec.