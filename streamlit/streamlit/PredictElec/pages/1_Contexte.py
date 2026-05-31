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

# Titre
#st.title("PredictElec")

# ### 1. Données
# Une introduction générale expliquant le contexte énergétique, les enjeux de la prédiction solaire et éolienne,  
# et la démarche globale du projet avec une présentation des données utilisées et leur sources.
# Nous présentons également dans les grandes lignes la pipeline mise en place entre l'extraction de données
# depuis les différentes sources et sa mise à disposition pour la partie analytique, dans notre cas, 
# la création de modèles de machine learning.
# ### 2. Machine Learning

st.markdown("""

Cette application présente les différentes étapes lors de la création d’un modèle Machine Learning
dans notre contexte énergétique, pour la prédiction de la production solaire et éolienne à partir 
des données historiques de production.

### ● Préparation de la donnée  
Exploration et nettoyage du dataset (timestamp, , production PV, vent, région…).  
Traitements appliqués : cleaning, enrichissement temporel, sélection de variables, etc.

### ● Modélisation  
Création de deux modèles :
- Régression Linéaire  
- Random Forest Regressor  
Avec évaluation et comparaison des performances.

### ● Prédiction  
Génération de prédictions solaires pour J, J+1, J+2, J+3 à partir de prévisions météo récupérées.  
L'utilisateur choisit :  
- le modèle  
- le jour à prédire  
- la région  

👈 Utilisez le menu latéral pour naviguer entre les pages.
""")
