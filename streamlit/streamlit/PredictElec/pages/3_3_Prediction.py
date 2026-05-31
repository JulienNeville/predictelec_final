from stylekit.stylekit import apply_tech_background, apply_topbar_theme, load_css, init_theme
from stylekit.menu import sidebar_menu

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

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

st.set_page_config(page_title="Prédiction", page_icon="", layout="wide")

st.title("Prédiction de la production photovoltaïque")
st.caption("Application des modèles sur des données prévisionnelles issues de la base de données.")

# ---------------------------------------------------
# Vérification session_state
# ---------------------------------------------------
required_keys = [
    "selected_features",
    "X_columns",
    "lin_model",
    "rf_model",
    "best_model"
]

missing = [k for k in required_keys if k not in st.session_state]
if missing:
    st.error(
        f"Contexte incomplet : clés manquantes {missing}. "
        "Veuillez repasser par les pages Préparation et Modélisation."
    )
    st.stop()

lin_model = st.session_state["lin_model"]
rf_model = st.session_state["rf_model"]
best_model = st.session_state["best_model"]

selected_features = st.session_state["selected_features"]
feature_order = st.session_state["X_columns"]

# ---------------------------------------------------
# Chargement des données de prédiction depuis la BDD
# ---------------------------------------------------
st.header("Chargement des données de prévision")

QUERY = """
SELECT
    code_region_insee,
    region,
    timestamp,
    ghi_wh_m2_15min
FROM pred_solaire_forecast_2
"""

@st.cache_data(ttl=1800, show_spinner="Chargement des données depuis la base...")
def load_forecast_data():
    engine = get_engine()
    df = pd.read_sql(QUERY, engine)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["date"] = df["timestamp"].dt.date
    return df

df_prev_raw = load_forecast_data()

st.success(f"{len(df_prev_raw)} lignes chargées depuis la BDD")

# ---------------------------------------------------
# Détection dynamique des dates disponibles
# ---------------------------------------------------
available_dates = sorted(df_prev_raw["date"].unique())

st.write(
    "**Dates disponibles pour la prédiction :**",
    ", ".join([d.strftime("%d/%m/%Y") for d in available_dates])
)

# ---------------------------------------------------
# Paramètres utilisateur
# ---------------------------------------------------
st.header("Paramètres de prédiction")

col1, col2 = st.columns(2)

with col1:
    chosen_date = st.selectbox(
        "Choisissez le jour à prédire :",
        available_dates,
        format_func=lambda d: d.strftime("%d/%m/%Y")
    )

with col2:
    model_choice = st.selectbox(
        "Modèle à utiliser :",
        ["Meilleur modèle", "Régression Linéaire", "Random Forest"]
    )

regions = sorted(df_prev_raw["code_region_insee"].unique())
regions_selected = st.multiselect(
    "Régions à prédire (codes INSEE) :",
    regions,
    default=regions
)

if not regions_selected:
    st.warning("Veuillez sélectionner au moins une région.")
    st.stop()

# ---------------------------------------------------
# Filtrage des données
# ---------------------------------------------------
df_prev = df_prev_raw[
    (df_prev_raw["date"] == chosen_date)
    & (df_prev_raw["code_region_insee"].isin(regions_selected))
].copy()

# ---------------------------------------------------
# Préparation des features
# ---------------------------------------------------
st.header("Préparation des features")

def prepare_X(df_input):
    df = df_input.copy()

    df["year"] = df["timestamp"].dt.year
    df["month"] = df["timestamp"].dt.month
    df["day"] = df["timestamp"].dt.day
    df["hour"] = df["timestamp"].dt.hour
    df["minute"] = df["timestamp"].dt.minute
    df["quarter_hour"] = (df["hour"] * 4) + (df["minute"] // 15)

    X = pd.DataFrame(index=df.index)

    for col in selected_features:
        if col in df.columns:
            X[col] = df[col]
        else:
            X[col] = 0

    X = X[feature_order]
    X = X.apply(pd.to_numeric, errors="coerce").fillna(0)

    return X

X_pred = prepare_X(df_prev)

st.dataframe(X_pred.head())

# ---------------------------------------------------
# Choix du modèle
# ---------------------------------------------------
st.header("Prédiction")

if model_choice == "Régression Linéaire":
    model = lin_model
    st.write("Modèle utilisé : **Régression Linéaire**")
elif model_choice == "Random Forest":
    model = rf_model
    st.write("Modèle utilisé : **Random Forest**")
else:
    model = best_model
    st.write("Modèle utilisé : **Meilleur modèle (automatique)**")

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

st.session_state["chosen_date"] = chosen_date
st.session_state["regions_selected"] = regions_selected
st.session_state["model_choice"] = model_choice

# ---------------------------------------------------
# Prédiction
# ---------------------------------------------------
df_pred = df_prev.copy()
# df_pred["pv_mwh_15min_pred"] = model.predict(X_pred)
df_pred["pv_mwh_15min_pred"] = (model.predict(X_pred))*4


# ---------------------------------------------------
# Résultats
# ---------------------------------------------------
st.subheader("Résultats par région et par période")

st.dataframe(
    df_pred[
        ["timestamp", "region", "code_region_insee",
         "ghi_wh_m2_15min", "pv_mwh_15min_pred"]
    ].sort_values(["code_region_insee", "timestamp"]),
    use_container_width=True
)

st.subheader("Résumé journalier")

agg = (
    df_pred
    .groupby(["date", "region", "code_region_insee"])["pv_mwh_15min_pred"]
    .sum()
    .reset_index(name="pv_mwh_total_MWh")
)

# Sauvegarde des résultats solaires pour la synthèse finale
st.session_state["solar_agg"] = agg
st.session_state["solar_predictions"] = df_pred

st.dataframe(agg, use_container_width=True)

total = agg["pv_mwh_total_MWh"].sum()
st.success(f"**Production totale : {total:.2f} MWh**")

# Graphiques
# Courbe de prédiction
st.subheader("Courbe de production par région")

plot_df = (
    df_pred.pivot_table(
        index="timestamp",
        columns="region",
        values="pv_mwh_15min_pred",
        aggfunc="sum",
    ).sort_index()
)

st.line_chart(plot_df)

# st.subheader("Courbe cumulée (Area Chart)")

# area_df = (
#     df_pred
#     .pivot_table(
#         index="timestamp",
#         columns="region",
#         values="pv_mwh_15min_pred",
#         aggfunc="sum"
#     )
#     .sort_index()
# )

# # pour bien stacker
# area_df = area_df.fillna(0).clip(lower=0)

# st.area_chart(area_df)

# st.subheader("Courbe cumulée (Area Chart – empilement réel)")

# # Données pivotées
# area_df = (
#     df_pred
#     .pivot_table(
#         index="timestamp",
#         columns="region",
#         values="pv_mwh_15min_pred",
#         aggfunc="sum"
#     )
#     .sort_index()
#     .fillna(0)
#     .clip(lower=0)
# )

# # Passage en format long (obligatoire pour Altair)
# area_long = (
#     area_df
#     .reset_index()
#     .melt(
#         id_vars="timestamp",
#         var_name="region",
#         value_name="production_MWh"
#     )
# )

# # Area chart empilé explicite
# chart = (
#     alt.Chart(area_long)
#     .mark_area()
#     .encode(
#         x=alt.X("timestamp:T", title="Heure"),
#         y=alt.Y(
#             "production_MWh:Q",
#             title="Production PV (MWh)",
#             stack="zero"   # ✅ EMPILAGE FORCÉ
#         ),
#         color=alt.Color("region:N", title="Région"),
#         tooltip=["timestamp", "region", "production_MWh"]
#     )
#     .properties(height=400)
# )

# st.altair_chart(chart, use_container_width=True)

st.subheader("Courbe cumulée total")

# --- 1) Données empilées par région ---
area_df = (
    df_pred
    .pivot_table(
        index="timestamp",
        columns="region",
        values="pv_mwh_15min_pred",
        aggfunc="sum"
    )
    .sort_index()
    .fillna(0)
    .clip(lower=0)
)

area_long = (
    area_df
    .reset_index()
    .melt(
        id_vars="timestamp",
        var_name="region",
        value_name="production_MWh"
    )
)

# --- 2) Données du total (toutes régions) ---
total_df = (
    area_df
    .sum(axis=1)
    .reset_index(name="total_MWh")
)

# --- Aire empilée ---
area_chart = (
    alt.Chart(area_long)
    .mark_area()
    .encode(
        x=alt.X("timestamp:T", title="Heure"),
        y=alt.Y(
            "production_MWh:Q",
            title="Production PV (MWh)",
            stack="zero"
        ),
        color=alt.Color("region:N", title="Région"),
        tooltip=[
            "timestamp:T",
            "region:N",
            alt.Tooltip("production_MWh:Q", title="Production (MWh)", format=",.2f"),
        ],
    )
)

# --- Ligne du total ---
total_line = (
    alt.Chart(total_df)
    .mark_line(color="black", strokeWidth=2)
    .encode(
        x="timestamp:T",
        y="total_MWh:Q",
        tooltip=[
            "timestamp:T",
            alt.Tooltip("total_MWh:Q", title="Total (MWh)", format=",.2f"),
        ],
    )
)

# --- Points sur le total ---
total_points = (
    alt.Chart(total_df)
    .mark_point(
        color="black",
        filled=True,
        size=50
    )
    .encode(
        x="timestamp:T",
        y="total_MWh:Q",
        tooltip=[
            "timestamp:T",
            alt.Tooltip("total_MWh:Q", title="Total (MWh)", format=",.2f"),
        ],
    )
)

# --- Combinaison finale ---
chart = (
    area_chart + total_line + total_points
).properties(height=450)

st.altair_chart(chart, use_container_width=True)


# st.subheader("Production totale par région (bar chart)")

# bar_df = (
#     df_pred.groupby("region")["pv_mwh_15min_pred"]
#     .sum()
#     .reset_index()
#     .sort_values("pv_mwh_15min_pred", ascending=False)
# )

# st.bar_chart(bar_df, x="region", y="pv_mwh_15min_pred")


# st.subheader("Production totale par région (bar chart)")

# bar_df = (
#     df_pred.groupby("region")["pv_mwh_15min_pred"]
#     .sum()
#     .reset_index()
#     .sort_values("pv_mwh_15min_pred", ascending=False)
# )

# chart = (
#     alt.Chart(bar_df)
#     .mark_bar(color="#2ecc71")  # vert
#     .encode(
#         x=alt.X("region:N", sort="-y", title="Région"),
#         y=alt.Y("pv_mwh_15min_pred:Q", title="Production totale (MWh)"),
#         tooltip=["region", "pv_mwh_15min_pred"]
#     )
#     .properties(height=400)
# )

# st.altair_chart(chart, use_container_width=True)


st.subheader("Production totale par région")

bar_df = (
    df_pred.groupby("region")["pv_mwh_15min_pred"]
    .sum()
    .reset_index()
    .sort_values("pv_mwh_15min_pred", ascending=False)
)

chart = (
    alt.Chart(bar_df)
    .mark_bar()
    .encode(
        x=alt.X("region:N", sort="-y", title="Région"),
        y=alt.Y("pv_mwh_15min_pred:Q", title="Production totale (MWh)"),
        color=alt.Color(
            "region:N",
            scale=alt.Scale(scheme="greens"),
            legend=None  # optionnel : enlève la légende si redondante
        ),
        tooltip=[
            "region",
            alt.Tooltip("pv_mwh_15min_pred:Q", title="Production (MWh)", format=",.2f")
        ]
    )
    .properties(height=400)
)

st.altair_chart(chart, use_container_width=True)