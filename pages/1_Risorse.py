"""Pagina anagrafica risorse."""

import json

import pandas as pd
import streamlit as st

import database as db
from database import init_db
from esco_skills import ESCO_SKILLS, SENIORITY_LEVELS, all_skills_flat

init_db()

st.set_page_config(page_title="Risorse", page_icon="👤", layout="wide")
st.title("👤 Anagrafica Risorse")

# ── helpers ──────────────────────────────────────────────────────────────────

def _refresh():
    st.session_state.pop("edit_risorsa_id", None)
    st.rerun()


# ── sidebar: form nuovo / modifica ───────────────────────────────────────────

def _form_risorsa(prefill: dict | None = None):
    is_edit = prefill is not None and prefill.get("id")
    title = "✏️ Modifica risorsa" if is_edit else "➕ Nuova risorsa"
    with st.sidebar:
        st.subheader(title)
        with st.form("form_risorsa", clear_on_submit=True):
            nome = st.text_input("Nome *", value=prefill.get("nome", "") if prefill else "")
            cognome = st.text_input("Cognome *", value=prefill.get("cognome", "") if prefill else "")
            seniority = st.selectbox(
                "Seniority *",
                SENIORITY_LEVELS,
                index=SENIORITY_LEVELS.index(prefill["seniority"])
                if prefill and prefill.get("seniority") in SENIORITY_LEVELS
                else 1,
            )
            line_manager = st.text_input(
                "Line Manager", value=prefill.get("line_manager", "") if prefill else ""
            )

            st.markdown("**Competenze ESCO**")
            selected_skills: list[str] = prefill.get("competenze", []) if prefill else []
            for category, skills in ESCO_SKILLS.items():
                chosen = st.multiselect(
                    category,
                    options=skills,
                    default=[s for s in selected_skills if s in skills],
                    key=f"skill_{category}",
                )
                for s in chosen:
                    if s not in selected_skills:
                        selected_skills.append(s)

            costo_std = st.number_input(
                "Costo giornaliero standard (€)",
                min_value=0.0,
                step=50.0,
                value=float(prefill.get("costo_giornaliero", 0)) if prefill else 0.0,
            )
            costo_marg = st.number_input(
                "Costo giornaliero marginato (€)",
                min_value=0.0,
                step=50.0,
                value=float(prefill.get("costo_marginato", 0)) if prefill else 0.0,
            )
            attivo = st.checkbox(
                "Risorsa attiva",
                value=bool(prefill.get("attivo", 1)) if prefill else True,
            )

            submitted = st.form_submit_button("💾 Salva")
            if submitted:
                if not nome.strip() or not cognome.strip():
                    st.error("Nome e Cognome sono obbligatori.")
                else:
                    # collect all selected skills across categories
                    all_sel: list[str] = []
                    for cat, skills in ESCO_SKILLS.items():
                        key = f"skill_{cat}"
                        all_sel.extend(st.session_state.get(key, []))

                    record = {
                        "nome": nome.strip(),
                        "cognome": cognome.strip(),
                        "seniority": seniority,
                        "line_manager": line_manager.strip(),
                        "competenze": list(dict.fromkeys(all_sel)),
                        "costo_giornaliero": costo_std,
                        "costo_marginato": costo_marg,
                        "attivo": int(attivo),
                    }
                    if is_edit:
                        record["id"] = prefill["id"]
                    db.upsert_risorsa(record)
                    st.success("Risorsa salvata!")
                    _refresh()

        if is_edit:
            if st.button("🗑️ Elimina risorsa", type="secondary"):
                db.delete_risorsa(prefill["id"])
                st.success("Risorsa eliminata.")
                _refresh()
        if is_edit and st.button("✖ Annulla"):
            _refresh()


# ── decide quale form mostrare ────────────────────────────────────────────────

edit_id = st.session_state.get("edit_risorsa_id")
if edit_id:
    _form_risorsa(db.get_risorsa(edit_id))
else:
    _form_risorsa()

# ── filtri ───────────────────────────────────────────────────────────────────

col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
with col_f1:
    filter_name = st.text_input("🔍 Cerca per nome / cognome")
with col_f2:
    filter_seniority = st.multiselect("Filtra seniority", SENIORITY_LEVELS)
with col_f3:
    filter_skill = st.selectbox("Filtra competenza", ["— tutte —"] + all_skills_flat())

# ── tabella ───────────────────────────────────────────────────────────────────

risorse = db.get_risorse()

if not risorse.empty:
    if filter_name:
        mask = (
            risorse["nome"].str.contains(filter_name, case=False, na=False)
            | risorse["cognome"].str.contains(filter_name, case=False, na=False)
        )
        risorse = risorse[mask]
    if filter_seniority:
        risorse = risorse[risorse["seniority"].isin(filter_seniority)]
    if filter_skill != "— tutte —":
        risorse = risorse[
            risorse["competenze"].apply(lambda c: filter_skill in c)
        ]

    display = risorse.copy()
    display["competenze"] = display["competenze"].apply(lambda c: ", ".join(c))
    display["attivo"] = display["attivo"].map({1: "✅", 0: "❌"})
    display = display.rename(
        columns={
            "id": "ID",
            "nome": "Nome",
            "cognome": "Cognome",
            "seniority": "Seniority",
            "line_manager": "Line Manager",
            "competenze": "Competenze",
            "costo_giornaliero": "Costo std (€/g)",
            "costo_marginato": "Costo marg (€/g)",
            "attivo": "Attivo",
        }
    )
    show_cols = [
        "ID", "Nome", "Cognome", "Seniority", "Line Manager",
        "Competenze", "Costo std (€/g)", "Costo marg (€/g)", "Attivo",
    ]
    st.dataframe(display[show_cols], use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Modifica / Elimina")
    sel_id = st.number_input(
        "Inserisci ID risorsa da modificare", min_value=1, step=1, value=1
    )
    if st.button("✏️ Carica risorsa selezionata"):
        st.session_state["edit_risorsa_id"] = int(sel_id)
        st.rerun()
else:
    st.info("Nessuna risorsa presente. Usare il form laterale per aggiungerne una.")
