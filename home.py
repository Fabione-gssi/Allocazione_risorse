"""Entry point — initialises the DB and shows a welcome dashboard summary."""

import streamlit as st

import auth
import database as db

st.set_page_config(
    page_title="Gestione Risorse & Allocazioni",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

auth.require_any_auth()

db.init_db()

st.title("📊 Gestione Risorse & Allocazioni")
st.markdown("Benvenuto nel sistema di gestione del team. Usa il menu laterale per navigare.")

# --- KPI cards -----------------------------------------------------------------
risorse_df = db.get_risorse(only_active=True)
progetti_df = db.get_progetti()
alloc_df = db.get_allocazioni()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Risorse attive", len(risorse_df))

with col2:
    attivi = len(progetti_df[progetti_df["stato"] == "In corso"]) if not progetti_df.empty else 0
    st.metric("Progetti in corso", attivi)

with col3:
    st.metric("Allocazioni totali", len(alloc_df))

with col4:
    if not alloc_df.empty and "costo_giornaliero" in alloc_df.columns:
        import pandas as pd

        alloc_df["data_inizio"] = pd.to_datetime(alloc_df["data_inizio"], errors="coerce")
        alloc_df["data_fine"] = pd.to_datetime(alloc_df["data_fine"], errors="coerce")
        alloc_df["giorni"] = (alloc_df["data_fine"] - alloc_df["data_inizio"]).dt.days.clip(lower=0)
        alloc_df["costo_totale"] = (
            alloc_df["costo_giornaliero"]
            * alloc_df["giorni"]
            * alloc_df["percentuale_allocazione"]
            / 100
        )
        totale = alloc_df["costo_totale"].sum()
        st.metric("Costo allocato (std)", f"€ {totale:,.0f}")
    else:
        st.metric("Costo allocato (std)", "€ 0")

st.divider()
st.markdown(
    """
### Sezioni disponibili

| Pagina | Descrizione |
|--------|-------------|
| 👤 **Risorse** | Anagrafica risorse, seniority, competenze ESCO con livelli di expertise, email, data assunzione |
| 📁 **Progetti** | Codici, tipo progetto, referenti, date, stato |
| 🔗 **Allocazioni** | Assegnazione risorse ↔ progetti con periodo e % FTE |
| 🔍 **Pianificazione** | Ricerca risorse disponibili per competenza, FTE, seniority |
| 📈 **Dashboard** | Gantt, disponibilità mensile, copertura competenze, costi |
| ⬆️ **Import / Export** | Upload Excel in blocco, download report |
"""
)
