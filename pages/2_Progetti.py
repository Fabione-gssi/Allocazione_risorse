"""Pagina gestione progetti."""

from datetime import date

import streamlit as st

import auth
import database as db
from database import init_db
from esco_skills import PROJECT_STATUS_OPTIONS

init_db()

st.set_page_config(page_title="Progetti", page_icon="📁", layout="wide")
st.title("📁 Gestione Progetti")

auth.require_admin()

def _refresh():
    st.session_state.pop("edit_progetto_id", None)
    st.rerun()


def _parse_date(val):
    if not val or val == "nan":
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except Exception:
        return None


def _form_progetto(prefill: dict | None = None):
    is_edit = prefill is not None and prefill.get("id")
    title = "✏️ Modifica progetto" if is_edit else "➕ Nuovo progetto"
    with st.sidebar:
        st.subheader(title)
        with st.form("form_progetto", clear_on_submit=True):
            nome_progetto = st.text_input(
                "Nome progetto *",
                value=prefill.get("nome_progetto", "") if prefill else "",
            )
            col1, col2 = st.columns(2)
            with col1:
                codice_interno = st.text_input(
                    "Codice interno",
                    value=prefill.get("codice_interno", "") if prefill else "",
                )
            with col2:
                codice_esterno = st.text_input(
                    "Codice esterno",
                    value=prefill.get("codice_esterno", "") if prefill else "",
                )
            risorse_df = db.get_risorse(only_active=True)
            risorse_map = {
                f"{r['cognome']} {r['nome']} (ID {r['id']})": r["id"]
                for _, r in risorse_df.iterrows()
            }
            referente_interno = st.selectbox(
                "Referente interno",
                list(risorse_map.keys())
            )
            referente_esterno = st.text_input(
                "Referente esterno",
                value=prefill.get("referente_esterno", "") if prefill else "",
            )
            data_inizio = st.date_input(
                "Data inizio",
                value=_parse_date(prefill.get("data_inizio")) if prefill else date.today(),
            )
            data_fine = st.date_input(
                "Data fine prevista",
                value=_parse_date(prefill.get("data_fine_prevista")) if prefill else None,
            )
            stato = st.selectbox(
                "Stato",
                PROJECT_STATUS_OPTIONS,
                index=PROJECT_STATUS_OPTIONS.index(prefill["stato"])
                if prefill and prefill.get("stato") in PROJECT_STATUS_OPTIONS
                else 1,
            )
            note = st.text_area(
                "Note", value=prefill.get("note", "") if prefill else "", height=80
            )

            submitted = st.form_submit_button("💾 Salva")
            if submitted:
                if not nome_progetto.strip():
                    st.error("Il nome del progetto è obbligatorio.")
                else:
                    record = {
                        "codice_interno": codice_interno.strip(),
                        "codice_esterno": codice_esterno.strip(),
                        "nome_progetto": nome_progetto.strip(),
                        "referente_interno": referente_interno.strip(),
                        "referente_esterno": referente_esterno.strip(),
                        "data_inizio": data_inizio.isoformat() if data_inizio else "",
                        "data_fine_prevista": data_fine.isoformat() if data_fine else "",
                        "stato": stato,
                        "note": note.strip(),
                    }
                    if is_edit:
                        record["id"] = prefill["id"]
                    db.upsert_progetto(record)
                    st.success("Progetto salvato!")
                    _refresh()

        if is_edit:
            if st.button("🗑️ Elimina progetto", type="secondary"):
                db.delete_progetto(prefill["id"])
                st.success("Progetto eliminato.")
                _refresh()
        if is_edit and st.button("✖ Annulla"):
            _refresh()


edit_id = st.session_state.get("edit_progetto_id")
if edit_id:
    _form_progetto(db.get_progetto(edit_id))
else:
    _form_progetto()

# ── filtri ────────────────────────────────────────────────────────────────────

col_f1, col_f2 = st.columns([3, 2])
with col_f1:
    filter_name = st.text_input("🔍 Cerca progetto")
with col_f2:
    filter_stato = st.multiselect("Filtra per stato", PROJECT_STATUS_OPTIONS)

# ── tabella ───────────────────────────────────────────────────────────────────

progetti = db.get_progetti()

if not progetti.empty:
    if filter_name:
        mask = (
            progetti["nome_progetto"].str.contains(filter_name, case=False, na=False)
            | progetti["codice_interno"].str.contains(filter_name, case=False, na=False)
            | progetti["codice_esterno"].str.contains(filter_name, case=False, na=False)
        )
        progetti = progetti[mask]
    if filter_stato:
        progetti = progetti[progetti["stato"].isin(filter_stato)]

    display = progetti.rename(
        columns={
            "id": "ID",
            "codice_esterno": "Cod. Esterno",
            "codice_interno": "Cod. Interno",
            "nome_progetto": "Nome Progetto",
            "referente_interno": "Ref. Interno",
            "referente_esterno": "Ref. Esterno",
            "data_inizio": "Inizio",
            "data_fine_prevista": "Fine Prevista",
            "stato": "Stato",
            "note": "Note",
        }
    )
    show_cols = [
        "ID", "Cod. Interno", "Cod. Esterno", "Nome Progetto",
        "Ref. Interno", "Ref. Esterno", "Inizio", "Fine Prevista", "Stato", "Note",
    ]
    st.dataframe(display[show_cols], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Modifica / Elimina")
    sel_id = st.number_input("Inserisci ID progetto da modificare", min_value=1, step=1, value=1)
    if st.button("✏️ Carica progetto selezionato"):
        st.session_state["edit_progetto_id"] = int(sel_id)
        st.rerun()
else:
    st.info("Nessun progetto presente. Usa il form laterale per crearne uno.")
