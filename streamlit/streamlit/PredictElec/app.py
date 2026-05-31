import streamlit as st
from stylekit.stylekit import apply_tech_background, apply_topbar_theme, load_css, init_theme, title_green
from stylekit.menu import sidebar_menu


# (1) CSS global
load_css()
st.sidebar.image("assets/logo_liora.png",  width=200)
#st.write("")
st.sidebar.divider()

# (2) Toggle & application du thème
# theme = init_theme(default="light")
theme = init_theme(default="light", show_toggle=False)

# (3) Surcharge "gris tech" uniquement si theme == 'dark'
apply_tech_background(theme)   # ton fond “page” en dark
apply_topbar_theme(theme)      # topbar sombre

# MENU LATERAL

sidebar_menu()

# -------------------------------
# CONFIG GÉNÉRALE DE L'APPLICATION
# -------------------------------
st.set_page_config(
    page_title="PredictElec",
    #page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------
# EN-TÊTE
# -------------------------------
st.markdown(
    """
    <h1 style="
        color: #90BB2B;
        font-size: 6rem;
        font-weight: 900;
        margin-top: -10px;
        line-height: 1.05;
    ">
        PredictElec
    </h1>
    """,
    unsafe_allow_html=True
)

st.subheader("Projet fil rouge - Cursus Data Engineer - JUN25_CONTINU_DE")
st.write("")
col1, col2, col3 = st.columns(3)

def member_block(image_path, name):
    #img_col, txt_col = st.columns([1, 2])
    img_col, txt_col = st.columns([0.2, 1.8])
    with img_col:
        st.image(image_path, width=30)
    
    with txt_col:
        st.markdown(
            f"""
            <div style="
                display: flex;
                align-items: center;
                margin: 0;
                padding: 0;
                font-size: 24px;
                font-weight: 600;
                text-align: left;
                font-family: 'Courier New', monospace;
            ">
                {name}
            </div>
            """,
            unsafe_allow_html=True
        )


with col1:
    member_block("assets/member1.png", "Caroline NONY")

with col2:
    member_block("assets/member2.png", "Julien NEVILLE")

with col3:
    member_block("assets/member3.png", "George CARDENAS")


# -------------------------------
# IMAGE (libre de droit/placeholder)
# -------------------------------
st.image(
    "assets/ban.png",
    width=1200
)


st.markdown("""
Bienvenue dans cette application Streamlit dédiée à la **modélisation et prédiction de la
production solaire/éolienne** à partir de données de **rayonnement solaire et de la vitesse du vent**.

👈 Utilisez le menu latéral pour naviguer entre les pages.
""")
