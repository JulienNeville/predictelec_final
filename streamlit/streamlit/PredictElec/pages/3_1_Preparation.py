import streamlit as st
from stylekit.stylekit import apply_tech_background, apply_topbar_theme, load_css, init_theme, title_green
from stylekit.menu import sidebar_menu
import pandas as pd
import numpy as np
import os
from db import get_engine


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

# ---------------------------------------------------
# Configuration locale
# ---------------------------------------------------
st.set_page_config(page_title="Préparation de la donnée", layout="wide")

st.title("Machine Learning – Solaire")
st.subheader("Préparation de la donnée")
st.caption("Chargement, nettoyage, enrichissement et préparation pour la modélisation. Chargement automatique de la production depuis la BDD.")

# ---------------------------------------------------
# Chargement BDD
# ---------------------------------------------------
# st.markdown("Chargement automatique de la production depuis la BDD")

QUERY = """
SELECT
    *
FROM prod_solaire_meteo_2
"""

@st.cache_data(ttl=3600)
def load_data():
    engine = get_engine()
    return pd.read_sql(QUERY, engine)

df = load_data()

# ---------------------------------------------------
# Aperçu
# ---------------------------------------------------
st.subheader("Aperçu des données")

##ajout info
# st.info(
#     """
#     **Description des colonnes**

#     **`ghi_wh_m2_15min`**  
#     Irradiation solaire globale horizontale reçue en **15 minutes**, exprimée en **Wh/m²**.  
#     Elle représente la quantité d’énergie solaire reçue par mètre carré sur une surface horizontale.

#     **`pv_mwh_15min`**  
#     Énergie électrique produite par l’installation photovoltaïque sur un intervalle de **15 minutes**, exprimée en **MWh**.
#     """
# )

with st.expander("Signification des colonnes"):
    st.markdown(
        """
        **`ghi_wh_m2_15min`**  
        Irradiation solaire globale horizontale cumulée sur 15 minutes  
        *(unité : Wh/m²)*

        **`pv_mwh_15min`**  
        Production électrique photovoltaïque sur 15 minutes  
        *(unité : MWh)*
        """
    )

# st.dataframe(df.head())
st.dataframe(df.tail())

# ---------------------------------------------------
# Nettoyage
# ---------------------------------------------------
st.header("Nettoyage")

# Timestamp → datetime
if "timestamp" in df.columns:
    df["timestamp"] = pd.to_datetime(df["timestamp"])
else:
    st.error("La colonne 'timestamp' est manquante ❌")
    st.stop()

# Suppression des doublons
initial_rows = len(df)
df.drop_duplicates(inplace=True)
cleaned_rows = len(df)
st.write(f"🟧 **Doublons supprimés :** {initial_rows - cleaned_rows}")

# Valeurs manquantes (NaN)
st.write("🟧 **Valeurs manquantes (NaN) par colonne :**")
st.dataframe(df.isna().sum())

# Remplacement des NaN par 0 (numériques uniquement)
if st.checkbox("Remplacer les valeurs manquantes (NaN) par 0"):
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].fillna(0)

    st.success("Les NaN des colonnes numériques ont été remplacés par 0")

# ---------------------------------------------------
# Enrichissement temporel
# ---------------------------------------------------
st.header("Extraction de features temporelles")

df["year"] = df["timestamp"].dt.year
df["month"] = df["timestamp"].dt.month
df["day"] = df["timestamp"].dt.day
df["hour"] = df["timestamp"].dt.hour
df["minute"] = df["timestamp"].dt.minute
df["quarter_hour"] = (df["hour"] * 4) + (df["minute"] // 15)

# st.dataframe(df.head())
st.dataframe(df.tail())

# ---------------------------------------------------
# Sélection des features
# ---------------------------------------------------
st.header("Sélection des variables explicatives")

default_features = [
    "code_region_insee",
    "ghi_wh_m2_15min",
    "month",
    "day",
    "hour",
    "quarter_hour",
]

all_features = df.columns.tolist()
target_col = "pv_mwh_15min"

selected_features = st.multiselect(
    "Sélectionnez les features à utiliser pour la modélisation",
    options=[col for col in all_features if col != target_col],
    default=default_features
)

# # ---------------------------------------------------
# # Normalisation
# # ---------------------------------------------------
# st.header("📏 Normalisation (optionnel)")

# normalize = st.checkbox("Normaliser les features sélectionnées")

# if normalize:
#     df_norm = df.copy()
#     for col in selected_features:
#         mean = df_norm[col].mean()
#         std = df_norm[col].std()
#         df_norm[col] = (df_norm[col] - mean) / std

#     st.success("Normalisation appliquée.")
#     st.dataframe(df_norm.head())
#     df_prepared = df_norm
# else:
#     df_prepared = df

df_prepared = df

# ---------------------------------------------------
# Sauvegarde en session_state
# ---------------------------------------------------
st.header("Sauvegarde pour la modélisation")

if st.button("Sauvegarder les données préparées"):
    st.session_state["prepared_df"] = df_prepared
    st.session_state["selected_features"] = selected_features
    st.session_state["target_col"] = target_col

    st.success("Données enregistrées dans la session et prêtes pour l'étape 2 (Modelisation).")