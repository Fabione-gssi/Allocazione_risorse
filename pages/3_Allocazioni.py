"""Pagina gestione allocazioni."""

from datetime import date

import pandas as pd
import streamlit as st

import database as db
from database import init_db
from esco_skills import ALLOCATION_STATUS_OPTIONS

init_db()

st.set_page_config(page_title="Allocazioni", page_icon="🔗", layout="wide")
st.title("🔗 Allocazioni Risorse ↔ Progetti")


def _refresh():
    st.session_state.pop("edit_alloc_id", None)
    st.rerun()


def _parse_date(val):
    if not val or str(val) == "nan":
        return date.today()
    try:
        return date.fromisoformat(str(val)[:10])
    except Exception:
        return date.today()


def _form_allocazione(prefill: dict | None = None):
    is_edit = prefill is not None and prefill.get("id")
    title = "✏️ Modifica allocazione" if is_edit else "➕ Nuova allocazione"

    risorse_df = db.get_risorse(only_active=True)
    progetti_df = db.get_progetti()

    if risorse_df.empty or progetti_df.empty:
        with st.sidebar:
            st.warning("Inserire prima almeno una risorsa e un progetto.")
        return

    risorse_map = {
        f"{r['cognome']} {r['nome']} (ID {r['id']})": r["id"]
        for _, r in risorse_df.iterrows()
    }
    progetti_map = {
        f"[{p['codice_interno']}] {p['nome_progetto']} (ID {p['id']})": p["id"]
        for _, p in progetti_df.iterrows()
    }

    with st.sidebar:
        st.subheader(title)
        with st.form("form_alloc", clear_on_submit=True):
            # default selections when editing
            default_r = next(
                (k for k, v in risorse_map.items() if v == prefill.get("risorsa_id")),
                list(risorse_map.keys())[0],
            ) if is_edit else list(risorse_map.keys())[0]
            default_p = next(
                (k for k, v in progetti_map.items() if v == prefill.get("progetto_id")),
                list(progetti_map.keys())[0],
            ) if is_edit else list(progetti_map.keys())[0]

            risorsa_key = st.selectbox("Risorsa *", list(risorse_map.keys()),
                                       index=list(risorse_map.keys()).index(default_r))
            progetto_key = st.selectbox("Progetto *", list(progetti_map.keys()),
                                        index=list(progetti_map.keys()).index(default_p))
            data_inizio = st.date_input(
                "Data inizio *",
                value=_parse_date(prefill.get("data_inizio")) if is_edit else date.today(),
            )
            data_fine = st.date_input(
                "Data fine *",
                value=_parse_date(prefill.get("data_fine")) if is_edit else date.today(),
            )
            perc = st.slider(
                "% Allocazione FTE",
                min_value=5,
                max_value=100,
                step=5,
                value=int(prefill.get("percentuale_allocazione", 100)) if is_edit else 100,
            )
            stato = st.selectbox(
                "Stato allocazione",
                ALLOCATION_STATUS_OPTIONS,
                index=ALLOCATION_STATUS_OPTIONS.index(prefill["stato"])
                if is_edit and prefill.get("stato") in ALLOCATION_STATUS_OPTIONS
                else 0,
            )
            note = st.text_area(
                "Note", value=prefill.get("note", "") if is_edit else "", height=80
            )

            submitted = st.form_submit_button("💾 Salva")
            if submitted:
                if data_fine < data_inizio:
                    st.error("La data fine deve essere successiva alla data inizio.")
                else:
                    record = {
                        "risorsa_id": risorse_map[risorsa_key],
                        "progetto_id": progetti_map[progetto_key],
                        "data_inizio": data_inizio.isoformat(),
                        "data_fine": data_fine.isoformat(),
                        "percentuale_allocazione": perc,
                        "stato": stato,
                        "note": note.strip(),
                    }
                    if is_edit:
                        record["id"] = prefill["id"]
                    db.upsert_allocazione(record)
                    st.success("Allocazione salvata!")
                    _refresh()

        if is_edit:
            if st.button("🗑️ Elimina allocazione", type="secondary"):
                db.delete_allocazione(prefill["id"])
                st.success("Allocazione eliminata.")
                _refresh()
        if is_edit and st.button("✖ Annulla"):
            _refresh()


# ── load edit prefill ─────────────────────────────────────────────────────────

edit_id = st.session_state.get("edit_alloc_id")
prefill = None
if edit_id:
    alloc_df = db.get_allocazioni()
    if not alloc_df.empty:
        rows = alloc_df[alloc_df["id"] == edit_id]
        if not rows.empty:
            prefill = rows.iloc[0].to_dict()

_form_allocazione(prefill)

# ── filtri ────────────────────────────────────────────────────────────────────

risorse_df = db.get_risorse(only_active=True)
progetti_df = db.get_progetti()

col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
with col_f1:
    risorsa_opts = ["— tutte —"] + (
        [f"{r['cognome']} {r['nome']}" for _, r in risorse_df.iterrows()]
        if not risorse_df.empty else []
    )
    filter_risorsa = st.selectbox("Filtra risorsa", risorsa_opts)
with col_f2:
    progetto_opts = ["— tutti —"] + (
        [p["nome_progetto"] for _, p in progetti_df.iterrows()]
        if not progetti_df.empty else []
    )
    filter_progetto = st.selectbox("Filtra progetto", progetto_opts)
with col_f3:
    filter_stato = st.multiselect("Filtra stato", ALLOCATION_STATUS_OPTIONS)

# ── tabella ───────────────────────────────────────────────────────────────────

alloc_df = db.get_allocazioni()

if not alloc_df.empty:
    if filter_risorsa != "— tutte —":
        alloc_df = alloc_df[alloc_df["risorsa_nome"] == filter_risorsa]
    if filter_progetto != "— tutti —":
        alloc_df = alloc_df[alloc_df["nome_progetto"] == filter_progetto]
    if filter_stato:
        alloc_df = alloc_df[alloc_df["stato"].isin(filter_stato)]

    # calcola costo
    alloc_df["data_inizio_dt"] = pd.to_datetime(alloc_df["data_inizio"], errors="coerce")
    alloc_df["data_fine_dt"] = pd.to_datetime(alloc_df["data_fine"], errors="coerce")
    alloc_df["giorni_lav"] = (
        (alloc_df["data_fine_dt"] - alloc_df["data_inizio_dt"]).dt.days * 5 / 7
    ).clip(lower=0).round(0).astype(int)
    alloc_df["costo_std"] = (
        alloc_df["costo_giornaliero"] * alloc_df["giorni_lav"] * alloc_df["percentuale_allocazione"] / 100
    ).round(0)
    alloc_df["costo_marg"] = (
        alloc_df["costo_marginato"] * alloc_df["giorni_lav"] * alloc_df["percentuale_allocazione"] / 100
    ).round(0)

    display = alloc_df.rename(
        columns={
            "id": "ID",
            "risorsa_nome": "Risorsa",
            "seniority": "Seniority",
            "nome_progetto": "Progetto",
            "codice_interno": "Cod. Int.",
            "data_inizio": "Inizio",
            "data_fine": "Fine",
            "percentuale_allocazione": "% FTE",
            "stato": "Stato",
            "giorni_lav": "Gg Lav.",
            "costo_std": "Costo Std (€)",
            "costo_marg": "Costo Marg (€)",
            "note": "Note",
        }
    )
    show_cols = [
        "ID", "Risorsa", "Seniority", "Progetto", "Cod. Int.",
        "Inizio", "Fine", "% FTE", "Stato", "Gg Lav.", "Costo Std (€)", "Costo Marg (€)", "Note",
    ]
    st.dataframe(display[show_cols], use_container_width=True, hide_index=True)

    # totali
    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("Righe visualizzate", len(alloc_df))
    col_t2.metric("Costo std totale (€)", f"{alloc_df['costo_std'].sum():,.0f}")
    col_t3.metric("Costo marginato totale (€)", f"{alloc_df['costo_marg'].sum():,.0f}")

    st.markdown("---")
    st.subheader("Modifica / Elimina")
    sel_id = st.number_input("Inserisci ID allocazione da modificare", min_value=1, step=1, value=1)
    if st.button("✏️ Carica allocazione selezionata"):
        st.session_state["edit_alloc_id"] = int(sel_id)
        st.rerun()
else:
    st.info("Nessuna allocazione presente. Usa il form laterale per crearne una.")
