import streamlit as st
import pandas as pd
import altair as alt

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

st.markdown(
    """
    <style>
    .kpi-box {
        border-radius: 10px;
        padding: 18px;
        text-align: left;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }

    .kpi-solar { background-color: #fff6cc; }
    .kpi-wind  { background-color: #e8f4fd; }
    .kpi-total { background-color: #e9f7ef; }

    .kpi-label {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 6px;
    }

    .kpi-value {
        font-size: 28px;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.set_page_config(page_title="Synthèse Multi‑Énergies", layout="wide")
st.title("Synthèse des productions prédites")
st.caption("Restitution des estimations solaires et éoliennes pour la journée sélectionnée.")

# #debug
# st.write("DEBUG session_state keys :", list(st.session_state.keys()))

# ---------------------------------------------------
# Vérification contexte
# ---------------------------------------------------
required_keys = ["solar_agg", "wind_predictions", "chosen_date", "regions_selected"]
missing = [k for k in required_keys if k not in st.session_state]

if missing:
    st.error(
        "Résultats incomplets. "
        "Veuillez d'abord effectuer les prédictions solaire et éolienne."
    )
    st.stop()

solar_agg = st.session_state["solar_agg"]
wind_df = st.session_state["wind_predictions"]
chosen_date = st.session_state["chosen_date"]

regions_selected = st.session_state["regions_selected"]
model_choice = st.session_state["model_choice"]


#####
regions_clean = [int(r) for r in regions_selected]

st.subheader("Contexte de la simulation")

col1, col3 = st.columns(2) #, col2

with col1:
    st.metric(
        label="Date sélectionnée",
        value=chosen_date.strftime("%d/%m/%Y")
    )

# with col2:
#     st.metric(
#         label="Modèle utilisé",
#         value=model_choice
#     )

with col3:
    st.metric(
        label="Nombre de régions",
        value=len(regions_clean)
    )

st.caption(
    "Régions sélectionnées : "
    + ", ".join(map(str, regions_clean))
)

# ---------------------------------------------------
# Agrégation éolienne journalière
# ---------------------------------------------------
wind_agg = (
    wind_df
    .groupby(["date", "region", "code_region_insee"])["eol_mwh_15min_pred"]
    .sum()
    .reset_index(name="wind_mwh_total_MWh")
)

# ---------------------------------------------------
# Fusion Solaire + Éolien
# ---------------------------------------------------
total_df = pd.merge(
    solar_agg,
    wind_agg,
    on=["date", "region", "code_region_insee"],
    how="outer"
).fillna(0)

total_df["total_mwh_MWh"] = (
    total_df["pv_mwh_total_MWh"] + total_df["wind_mwh_total_MWh"]
)

# ---------------------------------------------------
# KPIs globaux
# ---------------------------------------------------
st.header("Indicateurs clés – Journée sélectionnée")

# col1, col2, col3 = st.columns(3)

# with col1:
#     st.metric(
#         "Production solaire",
#         f"{total_df['pv_mwh_total_MWh'].sum():.2f} MWh"
#     )

# with col2:
#     st.metric(
#         "Production éolienne",
#         f"{total_df['wind_mwh_total_MWh'].sum():.2f} MWh"
#     )

# with col3:
#     st.metric(
#         "Production totale",
#         f"{total_df['total_mwh_MWh'].sum():.2f} MWh"
#     )

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        f"""
        <div class="kpi-box kpi-solar">
            <div class="kpi-label">Production solaire</div>
            <div class="kpi-value">{total_df['pv_mwh_total_MWh'].sum():.2f} MWh</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        f"""
        <div class="kpi-box kpi-wind">
            <div class="kpi-label">Production éolienne</div>
            <div class="kpi-value">{total_df['wind_mwh_total_MWh'].sum():.2f} MWh</div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        f"""
        <div class="kpi-box kpi-total">
            <div class="kpi-label">Production totale</div>
            <div class="kpi-value">{total_df['total_mwh_MWh'].sum():.2f} MWh</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ---------------------------------------------------
# Détails par région
# ---------------------------------------------------
st.header("Détail par région")

st.dataframe(
    total_df[[
        "region",
        "pv_mwh_total_MWh",
        "wind_mwh_total_MWh",
        "total_mwh_MWh"
    ]].sort_values("total_mwh_MWh", ascending=False),
    use_container_width=True
)

# ---------------------------------------------------
# Graphique simple – comparaison par région
# ---------------------------------------------------
st.subheader("Comparaison des productions par région")

# plot_df = total_df.melt(
#     id_vars=["region"],
#     value_vars=[
#         "pv_mwh_total_MWh",
#         "wind_mwh_total_MWh",
#         "total_mwh_MWh"
#     ],
#     var_name="source",
#     value_name="production_MWh"
# )

# chart = (
#     alt.Chart(plot_df)
#     .mark_bar()
#     .encode(
#         x=alt.X("region:N", title="Région"),
#         y=alt.Y("production_MWh:Q", title="Production (MWh)"),
#         color=alt.Color(
#             "source:N",
#             scale=alt.Scale(
#                 domain=[
#                     "pv_mwh_total_MWh",
#                     "wind_mwh_total_MWh",
#                     "total_mwh_MWh"
#                 ],
#                 range=["#f1c40f", "#3498db", "#2ecc71"]
#             ),
#             title="Source"
#         ),
#         tooltip=["region", "production_MWh"]
#     )
#     .properties(height=400)
# )

# st.altair_chart(chart, use_container_width=True)


# --- Barres empilées PV + Éolien + Total affiché en valeur ---

# 1) Préparation des données pour les barres empilées (sans le total)
plot_df = total_df.melt(
    id_vars=["region"],
    value_vars=[
        "pv_mwh_total_MWh",
        "wind_mwh_total_MWh",
    ],
    var_name="source",
    value_name="production_MWh"
)

# 2) Barres empilées photovoltaïque + éolien
bars = (
    alt.Chart(plot_df)
    .mark_bar()
    .encode(
        x=alt.X("region:N", title="Région"),
        y=alt.Y("production_MWh:Q", title="Production (MWh)"),
        color=alt.Color(
            "source:N",
            scale=alt.Scale(
                domain=[
                    "pv_mwh_total_MWh",
                    "wind_mwh_total_MWh",
                ],
                range=["#f1c40f", "#3498db"]
            ),
            title="Source"
        ),
        tooltip=[
            "region",
            "source",
            alt.Tooltip("production_MWh:Q", title="Production (MWh)")
        ]
    )
)

# 3) Affichage du total au sommet de la barre empilée
total_text = (
    alt.Chart(total_df)
    .mark_text(
        dy=-5,
        fontWeight="bold"
    )
    .encode(
        x=alt.X("region:N"),
        y=alt.Y("total_mwh_MWh:Q"),
        text=alt.Text("total_mwh_MWh:Q", format=",.0f"),
        tooltip=[
            "region",
            alt.Tooltip("total_mwh_MWh:Q", title="Total (MWh)")
        ]
    )
)

# 4) Combinaison finale
chart = (
    bars + total_text
).properties(height=400)

st.altair_chart(chart, use_container_width=True)