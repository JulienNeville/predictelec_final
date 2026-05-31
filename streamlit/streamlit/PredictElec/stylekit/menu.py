# stylekit/menu.py
import streamlit as st

def sidebar_menu():

    st.sidebar.markdown("## Navigation")

    # --- ACCUEIL ---
    st.sidebar.page_link("app.py", label="🔸Accueil")

    # --- CONTEXTE ---
    st.sidebar.page_link("pages/1_Contexte.py", label="🔸Introduction")

    # --- DONNÉES (collapsible) ---
    # with st.sidebar.expander("🔸Données", expanded=False):
    #     st.page_link("pages/2_Donnees.py", label="Présentation")
    #     st.page_link("pages/2_1_Les_sources.py", label="Les sources")
    #     st.page_link("pages/2_2_Exploration.py", label="Exploration")
    #     st.page_link("pages/2_3_Analyse.py", label="Analyse")
    #     st.page_link("pages/2_4_Pipeline.py", label="Pipeline")

    
    # --- MACHINE LEARNING (collapsible) ---
    with st.sidebar.expander("🔸Machine Learning", expanded=False):
    #with st.sidebar.expander(f"{ML_ICON} Machine Learning", expanded=False):
        #st.page_link("pages/3_Machine_learning.py", label="Présentation")
        st.page_link("pages/3_1_Preparation.py", label="Préparation")
        st.page_link("pages/3_2_Modelisation.py", label="Modélisation")
        st.page_link("pages/3_3_Prediction.py", label="Prédiction")
        st.page_link("pages/3_4_ML_Eolien.py", label="ML synthétisé Eolien")

    # --- CONCLUSION ---
    st.sidebar.page_link("pages/4_ML_Global.py", label="🔸Prédiction PV + EO")

    