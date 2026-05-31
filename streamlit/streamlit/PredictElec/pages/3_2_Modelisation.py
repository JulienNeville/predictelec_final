from stylekit.stylekit import apply_tech_background, apply_topbar_theme, load_css, init_theme, title_green
from stylekit.menu import sidebar_menu
import streamlit as st
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor

from sklearn.metrics import root_mean_squared_error, mean_absolute_error, r2_score
#mean_squared_error

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
# Configuration de la page
# ---------------------------------------------------
st.set_page_config(page_title="Modélisation", page_icon="", layout="wide")

st.title("Modélisation - Solaire")
st.markdown("Création, entraînement et évaluation des modèles (Régression Linéaire & Random Forest).")

# ---------------------------------------------------
# Vérification session_state
# ---------------------------------------------------
if "prepared_df" not in st.session_state:
    st.error("Les données ne sont pas disponibles. Veuillez passer par la page 2 (Préparation).")
    st.stop()

df = st.session_state["prepared_df"]
selected_features = st.session_state["selected_features"]
target_col = st.session_state["target_col"]

st.success("Données correctement récupérées depuis la page de préparation")

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

# ---------------------------------------------------
# Affichage des features et target
# ---------------------------------------------------
st.header("Features & variable cible")
st.write("### Features utilisées :", selected_features)
st.write("### Variable cible :", target_col)

# ---------------------------------------------------
# Séparation Train / Test
# ---------------------------------------------------
st.header("Séparation entraînement / test")

test_size = st.slider("Taille du jeu de test (%)", 5, 40, 20)
test_size = test_size / 100

X = df[selected_features]
y = df[target_col]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=test_size, shuffle=True, random_state=42
)

st.write(f"✔ Taille jeu train : {X_train.shape}")
st.write(f"✔ Taille jeu test : {X_test.shape}")

# ---------------------------------------------------
# Entraînement des modèles
# ---------------------------------------------------
st.header("Entraînement des modèles")

with st.expander("Signification des métriques de performance"):
    st.markdown(
        """
        **RMSE (Root Mean Squared Error)**  
        Racine de l’erreur quadratique moyenne.  
        Elle mesure l’écart moyen entre les valeurs prédites et les valeurs réelles, en donnant plus de poids aux grandes erreurs.  
        🔸 Plus le RMSE est faible, meilleur est le modèle *(unité : MWh)*.

        **MAE (Mean Absolute Error)**  
        Erreur absolue moyenne entre les prédictions et les observations.  
        Elle indique, en moyenne, de combien la prédiction se trompe.  
        🔸 Facile à interpréter, plus le MAE est faible, meilleur est le modèle *(unité : MWh)*.

        **R² (coefficient de détermination)**  
        Indique la proportion de la variance de la production expliquée par le modèle.  
        🔸 R² proche de 1 : très bon modèle  
        🔸 R² proche de 0 : modèle peu explicatif  
        🔸 R² négatif : modèle moins bon qu’une prédiction naïve
        """
    )

if st.button("Entraîner les modèles"):
    
    # -----------------
    # Régression linéaire
    # -----------------
    lin_model = LinearRegression()
    lin_model.fit(X_train, y_train)

    y_pred_lin = lin_model.predict(X_test)

    # Scores
    #lin_rmse = mean_squared_error(y_test, y_pred_lin, squared=False)
    lin_rmse = root_mean_squared_error(y_test, y_pred_lin)
    lin_mae  = mean_absolute_error(y_test, y_pred_lin)
    lin_r2   = r2_score(y_test, y_pred_lin)

    st.subheader("Régression Linéaire — Résultats")
    st.write(f"**RMSE :** {lin_rmse:.4f}")
    st.write(f"**MAE  :** {lin_mae:.4f}")
    st.write(f"**R²   :** {lin_r2:.4f}")

    # Coefficients
    coef_df = pd.DataFrame({
        "feature": selected_features,
        "coefficient": lin_model.coef_
    })

    st.write("**Coefficients du modèle**")
    st.dataframe(coef_df)

    # -----------------
    # Random Forest
    # -----------------
    rf_model = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        n_jobs=-1
    )
    rf_model.fit(X_train, y_train)

    y_pred_rf = rf_model.predict(X_test)

    #rf_rmse = mean_squared_error(y_test, y_pred_rf, squared=False)
    rf_rmse = root_mean_squared_error(y_test, y_pred_rf)
    rf_mae  = mean_absolute_error(y_test, y_pred_rf)
    rf_r2   = r2_score(y_test, y_pred_rf)

    st.subheader("Random Forest — Résultats")
    st.write(f"**RMSE :** {rf_rmse:.4f}")
    st.write(f"**MAE  :** {rf_mae:.4f}")
    st.write(f"**R²   :** {rf_r2:.4f}")

    # Importance des variables
    feat_importance = pd.DataFrame({
        "feature": selected_features,
        "importance": rf_model.feature_importances_
    }).sort_values("importance", ascending=False)

    st.write("**Importance des features (Random Forest)**")
    st.dataframe(feat_importance)

    # ---------------------------------------------------
    # Modèle choisi automatiquement (par RMSE)
    # ---------------------------------------------------
    st.header("Sélection automatique du meilleur modèle")

    if rf_rmse < lin_rmse:
        best_model = rf_model
        best_name = "Random Forest"
    else:
        best_model = lin_model
        best_name = "Régression Linéaire"

    st.success(f"Modèle sélectionné automatiquement : **{best_name}**")

    # Stockage en session_state
    st.session_state["best_model"] = best_model
    st.session_state["lin_model"] = lin_model
    st.session_state["rf_model"] = rf_model
    st.session_state["X_columns"] = selected_features

    st.info("Les modèles sont maintenant enregistrés et prêts pour l'étape 3 (Prédiction).")