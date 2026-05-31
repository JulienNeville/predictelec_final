from stylekit.stylekit import apply_tech_background, apply_topbar_theme, load_css, init_theme, title_green
from stylekit.menu import sidebar_menu

import streamlit as st
import pandas as pd
import numpy as np
from datetime import timedelta

# (1) CSS global
load_css()

# (2) Toggle & application du thème
theme = init_theme(default="light")

# (3) Surcharge "gris tech" uniquement si theme == 'dark'
apply_tech_background(theme)   # ton fond “page” en dark
apply_topbar_theme(theme)      # topbar sombre

# MENU LATERAL
sidebar_menu()

# ---------------------------------------------
# Config de page
# ---------------------------------------------
st.set_page_config(page_title="🔮 Prédiction", page_icon="🔮", layout="wide")
st.title("🔮 Prédiction de la production PV (J+1 · J+2 · J+3)")
st.caption("Génération d'un GHI prévisionnel synthétique, application du modèle, visualisations et exports.")

# ---------------------------------------------
# Vérifications des dépendances de session
# ---------------------------------------------
required_keys = ["prepared_df", "selected_features", "target_col", "X_columns", "lin_model", "rf_model", "best_model"]
missing = [k for k in required_keys if k not in st.session_state]
if missing:
    st.error(
        "❌ Contexte incomplet. Merci de repasser par :\n"
        "• Page 2 (Préparation) puis Page 3 (Modélisation)\n"
        f"Clés manquantes: {missing}"
    )
    st.stop()

df_hist = st.session_state["prepared_df"].copy()
selected_features = list(st.session_state["selected_features"])
target_col = st.session_state["target_col"]
feature_order = list(st.session_state["X_columns"])

lin_model = st.session_state["lin_model"]
rf_model  = st.session_state["rf_model"]
best_model = st.session_state["best_model"]

# ---------------------------------------------
# Infos de base
# ---------------------------------------------
st.success("Contexte récupéré ✔️ (données préparées + modèles)")

# Liste régions disponibles (codes INSEE)
if "code_region_insee" not in df_hist.columns:
    st.error("La colonne 'code_region_insee' est manquante dans les données préparées.")
    st.stop()

region_codes = sorted(df_hist["code_region_insee"].dropna().unique().tolist())

# Trouver la dernière date historique pour positionner J+1/J+2/J+3
if "timestamp" not in df_hist.columns:
    st.error("La colonne 'timestamp' est manquante dans les données préparées.")
    st.stop()

df_hist["timestamp"] = pd.to_datetime(df_hist["timestamp"])
base_date = df_hist["timestamp"].max().normalize()  # jour de référence (dernier jour présent)
dates_dict = {
    "J+1": base_date + timedelta(days=1),
    "J+2": base_date + timedelta(days=2),
    "J+3": base_date + timedelta(days=3),
}

# ---------------------------------------------
# Paramètres utilisateur
# ---------------------------------------------
left, right = st.columns([1.3, 1])

with left:
    st.subheader("🎛️ Paramètres de prédiction")

    day_choice = st.selectbox("Jour à prédire", options=["J+1", "J+2", "J+3"], index=0)
    day_date = dates_dict[day_choice]

    model_choice = st.selectbox(
        "Modèle à utiliser",
        options=["Meilleur (auto)", "Régression Linéaire", "Random Forest"],
        index=0
    )

    regions_selected = st.multiselect(
        "Sélectionnez une ou plusieurs régions (codes INSEE)",
        options=region_codes,
        default=region_codes[:3] if len(region_codes) >= 3 else region_codes
    )

with right:
    st.subheader("⚙️ Paramètres du GHI synthétique")
    daylight_start = st.slider("Heure de lever ~", 6.0, 9.0, 7.5, 0.25)
    daylight_end   = st.slider("Heure de coucher ~", 15.0, 18.0, 16.5, 0.25)
    peak_ghi       = st.slider("GHI max au zénith (Wh/m²/15min)", 200.0, 600.0, 420.0, 10.0)
    noise_level    = st.slider("Bruit relatif (%)", 0, 50, 15, 1)

# ---------------------------------------------
# Fonctions utilitaires
# ---------------------------------------------
def make_15min_range(day: pd.Timestamp) -> pd.DatetimeIndex:
    """Crée un index 15 min pour un jour donné [00:00 → 23:45]."""
    return pd.date_range(day, day + timedelta(days=1) - timedelta(minutes=15), freq="15min")

def synthetic_ghi_profile(dt: pd.Timestamp, start_h: float, end_h: float, peak: float) -> float:
    """
    GHI synthétique lisse type sinusoïde tronquée : 0 la nuit, pic à midi solaire ~.
    start_h/end_h: heures décimales de lever/coucher (ex: 7.5 → 07:30).
    peak: valeur crête ~Wh/m²/15min.
    """
    h = dt.hour + dt.minute / 60.0
    if h <= start_h or h >= end_h:
        return 0.0
    # Phasage de 0→π sur la fenêtre de jour
    x = (h - start_h) / (end_h - start_h)  # 0..1
    value = np.sin(np.pi * x) ** 1.7       # cloche un peu pointue
    return float(peak * value)

def region_scaling(code: int) -> float:
    """Facteur simple par région (stochastique mais stable via seed), pour différencier les profils."""
    rng = np.random.default_rng(seed=int(code) * 13 + 7)
    return float(rng.uniform(0.85, 1.15))

def add_noise(val: float, pct: int, rng: np.random.Generator) -> float:
    """Bruit multiplicatif ±pct%."""
    if val <= 0:
        return 0.0
    eps = rng.normal(0.0, pct / 100.0 * 0.5)  # sigma ~ pct/2
    return max(0.0, val * (1.0 + eps))

def build_forecast_df(day_date: pd.Timestamp, codes: list[int]) -> pd.DataFrame:
    """
    Construit un DataFrame prévisionnel :
    columns = ['timestamp','code_region_insee','ghi_wh_m2_15min_prevu']
    * 96 pas de 15 min par région sélectionnée
    """
    rng = np.random.default_rng(seed=int(day_date.strftime("%Y%m%d")))
    times = make_15min_range(day_date)
    rows = []
    for code in codes:
        scale = region_scaling(code)
        for t in times:
            ghi_base = synthetic_ghi_profile(t, daylight_start, daylight_end, peak_ghi)
            ghi_scaled = ghi_base * scale
            ghi_noisy = add_noise(ghi_scaled, noise_level, rng)
            rows.append((t, code, ghi_noisy))
    return pd.DataFrame(rows, columns=["timestamp", "code_region_insee", "ghi_wh_m2_15min_prevu"])

def detect_training_standardized(df_train: pd.DataFrame, feature_cols: list[str]) -> bool:
    """
    Détecte grossièrement si l’entraînement a été fait sur des features standardisées (z-score).
    Heuristique : ≥70% des features ont |mean|<0.1 et 0.8<std<1.2
    """
    if not feature_cols:
        return False
    means = df_train[feature_cols].mean(numeric_only=True)
    stds  = df_train[feature_cols].std(numeric_only=True)
    mask  = (means.abs() < 0.1) & (stds.between(0.8, 1.2))
    ratio = mask.mean() if len(mask) else 0.0
    return ratio >= 0.7

def prepare_X_for_prediction(df_prev: pd.DataFrame) -> pd.DataFrame:
    """
    Construit X_pred conforme aux features d’entraînement :
    - Ajoute features temporelles
    - Map 'ghi_wh_m2_15min_prevu' -> 'ghi_wh_m2_15min' si requis
    - Réordonne colonnes selon feature_order
    - Applique standardisation si l’entraînement était standardisé
    """
    df_prev = df_prev.copy()
    df_prev["timestamp"] = pd.to_datetime(df_prev["timestamp"])
    # Features temporelles
    df_prev["year"] = df_prev["timestamp"].dt.year
    df_prev["month"] = df_prev["timestamp"].dt.month
    df_prev["day"] = df_prev["timestamp"].dt.day
    df_prev["hour"] = df_prev["timestamp"].dt.hour
    df_prev["minute"] = df_prev["timestamp"].dt.minute
    df_prev["quarter_hour"] = (df_prev["hour"] * 4) + (df_prev["minute"] // 15)

    # Si 'ghi_wh_m2_15min' est attendu, le créer à partir du prévisionnel
    if "ghi_wh_m2_15min" in selected_features and "ghi_wh_m2_15min" not in df_prev.columns:
        if "ghi_wh_m2_15min_prevu" in df_prev.columns:
            df_prev["ghi_wh_m2_15min"] = df_prev["ghi_wh_m2_15min_prevu"]
        else:
            st.warning("⚠️ Colonne GHI prévisionnelle introuvable, remplissage à 0.")
            df_prev["ghi_wh_m2_15min"] = 0.0

    # Constituer X_pred avec les features sélectionnées
    X_pred = pd.DataFrame(index=df_prev.index)
    for col in selected_features:
        if col in df_prev.columns:
            X_pred[col] = df_prev[col]
        else:
            # Feature absente : remplir 0 pour rester compatible
            st.warning(f"⚠️ La feature '{col}' n'est pas disponible dans le jeu prévisionnel. Remplie à 0.")
            X_pred[col] = 0

    # S'assurer du bon ordre des features (celui utilisé à l'entraînement)
    # feature_order vient de st.session_state["X_columns"]
    for col in feature_order:
        if col not in X_pred.columns:
            X_pred[col] = 0
    X_pred = X_pred[feature_order]

    # Types numériques
    for col in X_pred.columns:
        X_pred[col] = pd.to_numeric(X_pred[col], errors="coerce").fillna(0)

    # Standardisation si on détecte un entraînement z-score
    std_trained = detect_training_standardized(df_hist, feature_order)
    if std_trained:
        means = df_hist[feature_order].mean(numeric_only=True)
        stds  = df_hist[feature_order].std(numeric_only=True).replace(0, 1.0)
        X_pred = (X_pred - means) / stds
        X_pred = X_pred.fillna(0.0)

    return X_pred

def pick_model(choice: str):
    if choice == "Régression Linéaire":
        return lin_model, "Régression Linéaire"
    elif choice == "Random Forest":
        return rf_model, "Random Forest"
    return best_model, "Meilleur (auto)"

# ---------------------------------------------
# Construction du dataset prévisionnel
# ---------------------------------------------
st.header("🧪 Génération des prévisions de GHI")
st.write(f"**Jour choisi :** {day_choice} → {day_date.date()}")

if not regions_selected:
    st.warning("Sélectionnez au moins **une** région pour générer les prévisions.")
    st.stop()

df_prev = build_forecast_df(day_date, regions_selected)
st.dataframe(df_prev.head(10), use_container_width=True)

# ---------------------------------------------
# Application du modèle sélectionné
# ---------------------------------------------
st.header("🤖 Prédiction PV à partir des GHI prévus")

model, model_label = pick_model(model_choice)
st.write(f"**Modèle utilisé :** {model_label}")

# Construire X_pred (features) en conformité avec l'entraînement
X_pred = prepare_X_for_prediction(df_prev)

# Prédiction
try:
    y_pred = model.predict(X_pred)
except Exception as e:
    st.error(f"Erreur pendant la prédiction : {e}")
    st.stop()

df_pred = df_prev.copy()
df_pred["pv_mwh_15min_pred"] = y_pred

# ---------------------------------------------
# Agrégations & tableaux
# ---------------------------------------------
st.subheader("📈 Résultats par pas de 15 minutes")
st.dataframe(
    df_pred[["timestamp", "code_region_insee", "ghi_wh_m2_15min_prevu", "pv_mwh_15min_pred"]]
    .sort_values(["code_region_insee", "timestamp"]),
    use_container_width=True
)

st.subheader("🧮 Agrégation journalière")
agg = (
    df_pred
    .assign(date=lambda d: d["timestamp"].dt.date)
    .groupby(["date", "code_region_insee"], as_index=False)["pv_mwh_15min_pred"].sum()
    .rename(columns={"pv_mwh_15min_pred": "pv_mwh_total_MWh"})
)
st.dataframe(agg, use_container_width=True)

total_day = agg["pv_mwh_total_MWh"].sum()
st.success(f"**Production totale (toutes régions sélectionnées) — {day_choice} : {total_day:.2f} MWh**")

# ---------------------------------------------
# Visualisations
# ---------------------------------------------
st.subheader("📊 Courbe PV prédite (par région)")
# Pivot pour une multi-série (régions en colonnes)
plot_df = (
    df_pred
    .pivot_table(index="timestamp", columns="code_region_insee", values="pv_mwh_15min_pred", aggfunc="sum")
    .sort_index()
)
st.line_chart(plot_df)

# ---------------------------------------------
# Export CSV
# ---------------------------------------------
st.subheader("📥 Export des prédictions")
csv_bytes = (
    df_pred[["timestamp", "code_region_insee", "ghi_wh_m2_15min_prevu", "pv_mwh_15min_pred"]]
    .sort_values(["code_region_insee", "timestamp"])
    .to_csv(index=False)
    .encode("utf-8")
)
st.download_button(
    label="💾 Télécharger le CSV des prédictions",
    data=csv_bytes,
    file_name=f"predictions_pv_{day_choice}_{str(day_date.date())}.csv",
    mime="text/csv"
)

st.info("Astuce : ajustez les curseurs (lever/coucher, pic GHI, bruit) pour simuler différents scénarios météo.")
