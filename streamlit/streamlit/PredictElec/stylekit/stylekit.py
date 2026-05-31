# stylekit/stylekit.py
from pathlib import Path
import streamlit as st

# ---------- Chargement CSS de base ----------
def load_css(path: str = "stylekit/style.css"):
    css = Path(path).read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# ---------- Titres verts ----------
def title_green(text: str, size: float = 4.0):
    st.markdown(
        f"""
        <h1 style="
            color:#2E8B57;
            font-size:{size}rem;
            font-weight:800;
            margin-top:0;">
            {text}
        </h1>
        """,
        unsafe_allow_html=True
    )

# ---------- Overrides CSS pour le dark mode ----------

_DARK_CSS = """
<style>
:root {
  /* surfaces plus sombres */
  --surface: #0B1220;        /* légèrement plus sombre que #0F172A */
  --surface-alt: #0E1526;    /* couche cartes */
  --border: #1C2436;

  /* texte très clair pour contraste AA/AAA */
  --text: #F5F7FA;           /* près du blanc */
  --text-muted: #B8C0CC;

  /* primaire (vert) plus lumineuse en sombre */
  --brand-primary: #3CD58D;      /* vert plus vif */
  --brand-primary-600: #2EB977;  /* hover/active */
  --brand-primary-200: #1F3F33;  /* teinte pâle pour badges, backgrounds */
}
</style>
"""

def apply_theme(theme: str = "light"):
    """Injecte les variables CSS du thème courant."""
    if theme == "dark":
        st.markdown(_DARK_CSS, unsafe_allow_html=True)

# ---------- Synchronisation des librairies de graphiques ----------
def setup_plotly(theme: str):
    try:
        import plotly.io as pio
        palette = ["#2E8B57","#22A06B","#009E73","#8BC34A","#3CB371","#006400"]
        base = "plotly_dark" if theme == "dark" else "plotly_white"
        pio.templates["brand"] = pio.templates[base]
        pio.templates["brand"].layout.colorway = palette
        pio.templates["brand"].layout.paper_bgcolor = "rgba(0,0,0,0)"
        pio.templates["brand"].layout.plot_bgcolor  = "rgba(0,0,0,0)"
        pio.templates["brand"].layout.font.color    = "#F3F4F6" if theme=="dark" else "#1F2937"
        pio.templates.default = "brand"
    except Exception:
        pass

def setup_altair(theme: str):
    try:
        import altair as alt
        palette = ["#2E8B57","#22A06B","#009E73","#8BC34A","#3CB371","#006400"]
        def _theme():
            return {
              "config": {
                "view": {"stroke": "transparent"},
                "range": {"category": palette},
                "background": "transparent",
                "axis": {
                  "labelColor": "#F3F4F6" if theme=="dark" else "#1F2937",
                  "titleColor": "#F3F4F6" if theme=="dark" else "#1F2937"
                },
                "legend": {
                  "labelColor": "#F3F4F6" if theme=="dark" else "#1F2937",
                  "titleColor": "#F3F4F6" if theme=="dark" else "#1F2937"
                }
              }
            }
        alt.themes.register('brand', _theme)
        alt.themes.enable('brand')
    except Exception:
        pass

def setup_matplotlib(theme: str):
    try:
        import matplotlib.pyplot as plt
        plt.rcParams.update({
            "axes.prop_cycle": plt.cycler(color=["#2E8B57","#22A06B","#009E73","#8BC34A","#3CB371","#006400"]),
            "figure.facecolor": "white" if theme=="light" else "#111827",
            "axes.facecolor": "white" if theme=="light" else "#111827",
            "axes.edgecolor": "#E5E7EB" if theme=="light" else "#1F2937",
            "axes.labelcolor": "#1F2937" if theme=="light" else "#F3F4F6",
            "text.color": "#1F2937" if theme=="light" else "#F3F4F6",
            "xtick.color": "#1F2937" if theme=="light" else "#F3F4F6",
            "ytick.color": "#1F2937" if theme=="light" else "#F3F4F6",
            "grid.color":  "#E5E7EB" if theme=="light" else "#1F2937",
        })
    except Exception:
        pass

def setup_charts(theme: str):
    setup_plotly(theme)
    setup_altair(theme)
    setup_matplotlib(theme)

# ---------- Initialisation / toggle ----------
# def init_theme(default: str = "light") -> str:
#     """
#     Affiche un toggle sidebar, applique le thème (CSS + charts),
#     et persiste la préférence en session.
#     """
#     prior = st.session_state.get("_theme", default)
#     dark_default = prior == "dark"
#     dark = st.sidebar.toggle("🌙 Mode sombre", value=dark_default)
#     theme = "dark" if dark else "light"
#     st.session_state["_theme"] = theme

#     apply_theme(theme)
#     setup_charts(theme)
#     return theme

def init_theme(default: str = "light", show_toggle: bool = False) -> str:
    prior = st.session_state.get("_theme", default)

    if show_toggle:
        dark_default = prior == "dark"
        dark = st.sidebar.toggle("🌙 Mode sombre", value=dark_default)
        theme = "dark" if dark else "light"
    else:
        theme = prior

    st.session_state["_theme"] = theme
    apply_theme(theme)
    setup_charts(theme)
    return theme

# ... tes fonctions existantes: load_css(), init_theme(), etc.

# --- Surcharge "page active gris tech" (uniquement si theme == 'dark') ---
_PAGE_TECH_BG_CSS = """
<style>
:root{
  --page-bg-tech:#1f242c;
  --page-bg-tech-contrast:#F5F7FA;
  --page-bg-tech-card:#252b35;
  --page-bg-tech-border:#303846;
}

/* Conteneur de la page (hors sidebar) */
div[data-testid="stAppViewContainer"],
main[data-testid="stAppViewContainer"] {
  background: var(--page-bg-tech) !important;
}

/* Zone principale */
div[data-testid="stMain"], .block-container {
  background: transparent !important;
  color: var(--page-bg-tech-contrast) !important;
}

/* Cartes/encadrés personnalisés */
.block {
  background: var(--page-bg-tech-card) !important;
  border: 1px solid var(--page-bg-tech-border) !important;
  color: var(--page-bg-tech-contrast) !important;
}

/* Titres & textes: garantir le contraste */
h1,h2,h3,h4,h5,p,span,li,label,code,pre {
  color: var(--page-bg-tech-contrast) !important;
}

/* Metrics & tables */
[data-testid="stMetric"]{
  background: var(--page-bg-tech-card) !important;
  border: 1px solid var(--page-bg-tech-border) !important;
}
thead tr th{
  background: var(--page-bg-tech-card) !important;
  color: var(--page-bg-tech-contrast) !important;
}

/* Bannière: micro-ajustement */
.hero img{
  filter: brightness(.95) contrast(1.03);
}

/* Liens hover */
div[data-testid="stMain"] a:hover {
  color: var(--brand-primary) !important;
}
</style>
"""

def apply_tech_background(theme: str):
    """Applique le fond 'gris tech' uniquement si theme == 'dark'."""
    if theme.lower() == "dark":
        st.markdown(_PAGE_TECH_BG_CSS, unsafe_allow_html=True)


_TOPBAR_DARK_CSS = """
<style>
:root{
  --topbar-bg: #0E1526;
  --topbar-text: #F5F7FA;
  --topbar-border: #1C2436;
}
header[data-testid="stHeader"],
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"]{
  background: var(--topbar-bg) !important;
  color: var(--topbar-text) !important;
  border-bottom: 1px solid var(--topbar-border) !important;
  box-shadow: none !important;
}
header[data-testid="stHeader"] *,
div[data-testid="stToolbar"] *,
div[data-testid="stDecoration"] *,
div[data-testid="stStatusWidget"] *{
  color: var(--topbar-text) !important;
  fill: var(--topbar-text) !important;
}
header[data-testid="stHeader"] button,
div[data-testid="stToolbar"] button{
  color: var(--topbar-text) !important;
  background: transparent !important;
  border: 1px solid rgba(255,255,255,0.15) !important;
  border-radius: 8px !important;
}
header[data-testid="stHeader"] button:hover,
div[data-testid="stToolbar"] button:hover{
  background: rgba(255,255,255,0.08) !important;
}
header[data-testid="stHeader"]::before,
header[data-testid="stHeader"]::after{ display:none !important; }
</style>
"""

def apply_topbar_theme(theme: str):
    """Thématise la topbar uniquement en mode sombre."""
    if theme.lower() == "dark":
        st.markdown(_TOPBAR_DARK_CSS, unsafe_allow_html=True)