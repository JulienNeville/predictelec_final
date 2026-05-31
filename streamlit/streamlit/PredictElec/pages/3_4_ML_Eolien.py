import streamlit as st
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import root_mean_squared_error

from db import get_engine
from stylekit.stylekit import load_css, init_theme, apply_tech_background, apply_topbar_theme
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

st.set_page_config(page_title="ML Éolien", layout="wide")
st.title("Machine Learning – Éolien")
st.caption("Préparation, entraînement et estimation automatique de la production éolienne.")

# ---------------------------------------------------
# Vérification contexte solaire
# ---------------------------------------------------
required_keys = ["chosen_date", "regions_selected", "model_choice"]
missing = [k for k in required_keys if k not in st.session_state]

if missing:
    st.error(
        "Contexte solaire manquant. "
        "Veuillez d'abord effectuer la prédiction solaire."
    )
    st.stop()

chosen_date = st.session_state["chosen_date"]
regions_selected = st.session_state["regions_selected"]
model_choice = st.session_state["model_choice"]

# ---------------------------------------------------
# Chargement données éoliennes historiques
# ---------------------------------------------------
st.header("Chargement des données éoliennes historiques")

# st.info(
#     f"Contexte récupéré — Date : {chosen_date}, "
#     f"Régions : {regions_selected}, "
#     f"Modèle : {model_choice}"
# )

#####
regions_clean = [int(r) for r in regions_selected]

st.subheader("Contexte de la simulation")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Date sélectionnée",
        value=chosen_date.strftime("%d/%m/%Y")
    )

with col2:
    st.metric(
        label="Modèle utilisé",
        value=model_choice
    )

with col3:
    st.metric(
        label="Nombre de régions",
        value=len(regions_clean)
    )

st.caption(
    "Régions sélectionnées : "
    + ", ".join(map(str, regions_clean))
)

QUERY_HISTO = "SELECT * FROM prod_eolien_meteo_2"

@st.cache_data(ttl=3600)
def load_wind_data():
    engine = get_engine()
    df = pd.read_sql(QUERY_HISTO, engine)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

df = load_wind_data()
st.success(f"{len(df)} lignes chargées")

# ---------------------------------------------------
# Nettoyage (NaN → 0 par défaut)
# ---------------------------------------------------
numeric_cols = df.select_dtypes(include=[np.number]).columns
df[numeric_cols] = df[numeric_cols].fillna(0)

# ---------------------------------------------------
# Feature engineering temporel
# ---------------------------------------------------
df["month"] = df["timestamp"].dt.month
df["day"] = df["timestamp"].dt.day
df["hour"] = df["timestamp"].dt.hour
df["quarter_hour"] = (df["hour"] * 4)

# ---------------------------------------------------
# Sélection des variables
# ---------------------------------------------------
st.header("Sélection des variables explicatives")

with st.expander("Signification de la variable vitesse du vent (éolien)"):
    st.markdown(
        """
        **`vitesse_vent_15min`**  
        Vitesse moyenne du vent mesurée sur un intervalle de **15 minutes**  
        *(unité : m/s)*

        Dans un contexte **éolien**, cette variable est **fondamentale** :
        - la production d’une éolienne dépend directement de la vitesse du vent
        - l’énergie produite est proportionnelle **au cube de la vitesse du vent**
        - de faibles variations de vent peuvent entraîner de fortes variations de production

        """
    )

target_col = "eol_mwh_15min"

default_features = [
    "code_region_insee",
    "vitesse_vent_15min",
    "month",
    "day",
    "hour",
    "quarter_hour",
]

selected_features = st.multiselect(
    "Variables explicatives",
    options=[c for c in df.columns if c != target_col],
    default=default_features
)

if not selected_features:
    st.warning("Veuillez sélectionner au moins une variable.")
    st.stop()

# ---------------------------------------------------
# Split Train / Test
# ---------------------------------------------------
st.header("Paramètres d'entraînement")

test_size = st.slider("Taille du jeu de test (%)", 5, 40, 20) / 100

# ---------------------------------------------------
# Entraînement
# ---------------------------------------------------
if st.button("Lancer l'entraînement"):

    X = df[selected_features]
    y = df[target_col]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42
    )

    # Modèles
    lin_model = LinearRegression()
    rf_model = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)

    lin_model.fit(X_train, y_train)
    rf_model.fit(X_train, y_train)

    # Évaluation
    rmse_lin = root_mean_squared_error(y_test, lin_model.predict(X_test))
    rmse_rf = root_mean_squared_error(y_test, rf_model.predict(X_test))

    best_model = rf_model if rmse_rf < rmse_lin else lin_model

    st.success("Entraînement terminé") # – meilleur modèle sélectionné")

    # ---------------------------------------------------
    # Chargement forecast éolien
    # ---------------------------------------------------
    QUERY_FORECAST = """
    SELECT *
    FROM pred_eolien_forecast_2
    """

    engine = get_engine()
    df_forecast = pd.read_sql(QUERY_FORECAST, engine)
    df_forecast["timestamp"] = pd.to_datetime(df_forecast["timestamp"])
    df_forecast["date"] = df_forecast["timestamp"].dt.date

    df_forecast = df_forecast[
        (df_forecast["date"] == chosen_date)
        & (df_forecast["code_region_insee"].isin(regions_selected))
    ]

    # Feature engineering forecast
    df_forecast["month"] = df_forecast["timestamp"].dt.month
    df_forecast["day"] = df_forecast["timestamp"].dt.day
    df_forecast["hour"] = df_forecast["timestamp"].dt.hour
    df_forecast["quarter_hour"] = (df_forecast["hour"] * 4)

    X_pred = df_forecast[selected_features].fillna(0)

    # Prédiction
    # df_forecast["eol_mwh_15min_pred"] = best_model.predict(X_pred)
    df_forecast["eol_mwh_15min_pred"] = (best_model.predict(X_pred))*4


    # Sauvegarde pour page finale
    st.session_state["wind_predictions"] = df_forecast
    st.session_state["wind_model"] = best_model

    st.info("Estimation éolienne calculée et stockée pour la page de synthèse.")