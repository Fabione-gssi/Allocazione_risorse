"""Pagina anagrafica risorse."""

import streamlit as st

import database as db
from database import init_db
from esco_skills import ESCO_SKILLS, EXPERTISE_LEVELS, SENIORITY_LEVELS, all_skills_flat

init_db()

st.set_page_config(page_title="Risorse", page_icon="👤", layout="wide")
st.title("👤 Anagrafica Risorse")

# ── helpers ───────────────────────────────────────────────────────────────────

def _clear_form_state():
    """Rimuove dal session state tutti i valori pre-caricati del form."""
    st.session_state.pop("edit_risorsa_id", None)
    st.session_state.pop("_prefill_loaded_id", None)
    for category, skills in ESCO_SKILLS.items():
        st.session_state.pop(f"skill_{category}", None)
        for skill in skills:
            st.session_state.pop(f"expertise_{skill}", None)
    for key in ("f_nome", "f_cognome", "f_seniority", "f_line_manager",
                "f_costo_std", "f_costo_marg", "f_attivo"):
        st.session_state.pop(key, None)


def _refresh():
    _clear_form_state()
    st.rerun()


def _prefill_session_state(risorsa: dict):
    """Scrive i valori della risorsa nel session state prima del render del form."""
    if st.session_state.get("_prefill_loaded_id") == risorsa["id"]:
        return  # già caricato, non sovrascrivere le modifiche dell'utente
    competenze = risorsa.get("competenze") or {}
    if isinstance(competenze, list):
        competenze = {s: 0 for s in competenze}
    for category, skills in ESCO_SKILLS.items():
        selected = [s for s in skills if s in competenze]
        st.session_state[f"skill_{category}"] = selected
        for skill in selected:
            st.session_state[f"expertise_{skill}"] = competenze.get(skill, 0)
    st.session_state["f_nome"] = risorsa.get("nome", "")
    st.session_state["f_cognome"] = risorsa.get("cognome", "")
    st.session_state["f_seniority"] = risorsa.get("seniority", SENIORITY_LEVELS[1])
    st.session_state["f_line_manager"] = risorsa.get("line_manager", "")
    st.session_state["f_costo_std"] = float(risorsa.get("costo_giornaliero", 0) or 0)
    st.session_state["f_costo_marg"] = float(risorsa.get("costo_marginato", 0) or 0)
    st.session_state["f_attivo"] = bool(risorsa.get("attivo", 1))
    st.session_state["_prefill_loaded_id"] = risorsa["id"]


# ── sidebar: form nuovo / modifica ───────────────────────────────────────────

def _form_risorsa(prefill: dict | None = None):
    is_edit = prefill is not None and prefill.get("id")

    if is_edit:
        _prefill_session_state(prefill)

    # lista line manager esistenti per la selectbox
    risorse_all = db.get_risorse()
    lm_options = [""] + sorted(
        {r for r in risorse_all["nome"] + " " + risorse_all["cognome"]}
        if not risorse_all.empty else []
    )
    # se il line manager attuale non è nella lista (testo libero storico), aggiungilo
    current_lm = st.session_state.get("f_line_manager", "")
    if current_lm and current_lm not in lm_options:
        lm_options.insert(1, current_lm)

    with st.sidebar:
        st.subheader("✏️ Modifica risorsa" if is_edit else "➕ Nuova risorsa")
        st.text_input("Nome *", key="f_nome")
        st.text_input("Cognome *", key="f_cognome")
        
        seniority_idx = 1
        cur_seniority = st.session_state.get("f_seniority", SENIORITY_LEVELS[1])
        if cur_seniority in SENIORITY_LEVELS:
            seniority_idx = SENIORITY_LEVELS.index(cur_seniority)
        st.selectbox("Seniority *", SENIORITY_LEVELS, index=seniority_idx, key="f_seniority")

        lm_idx = lm_options.index(current_lm) if current_lm in lm_options else 0
        st.selectbox("Line Manager", lm_options, index=lm_idx, key="f_line_manager")

        st.markdown("**Competenze ESCO**")
        for category, skills in ESCO_SKILLS.items():
            n_sel = len(st.session_state.get(f"skill_{category}", []))
            label = f"{category} ({n_sel} selezionate)" if n_sel else category
            with st.expander(label, expanded=n_sel > 0):
                st.multiselect(
                    "Seleziona competenze",
                    options=skills,
                    key=f"skill_{category}",
                    label_visibility="collapsed",
                )
                for skill in st.session_state.get(f"skill_{category}", []):
                    st.selectbox(
                        f"↳ {skill}",
                        options=list(EXPERTISE_LEVELS.keys()),
                        format_func=lambda v: EXPERTISE_LEVELS[v],
                        index=cur_level,
                        key=f"expertise_{skill}",
                    )

        st.number_input(
            "Costo giornaliero standard (€)", min_value=0.0, step=50.0, key="f_costo_std",
        )
        st.number_input(
            "Costo giornaliero marginato (€)", min_value=0.0, step=50.0, key="f_costo_marg",
        )
        st.checkbox("Risorsa attiva", key="f_attivo")
        
        if st.button("💾 Salva", type="primary", use_container_width=True):
            nome_val = st.session_state.get("f_nome", "").strip()
            cognome_val = st.session_state.get("f_cognome", "").strip()
            if not nome_val or not cognome_val:
                st.error("Nome e Cognome sono obbligatori.")
            else:
                competenze_dict: dict[str, int] = {}
                for cat in ESCO_SKILLS:
                    for skill in st.session_state.get(f"skill_{cat}", []):
                        if skill not in competenze_dict:
                            competenze_dict[skill] = st.session_state.get(f"expertise_{skill}", 0)
                            
                record = {
                    "nome": nome_val,
                    "cognome": cognome_val,
                    "seniority": st.session_state.get("f_seniority", SENIORITY_LEVELS[1]),
                    "line_manager": st.session_state.get("f_line_manager", ""),
                    "competenze": competenze_dict,
                    "costo_giornaliero": st.session_state.get("f_costo_std", 0.0),
                    "costo_marginato": st.session_state.get("f_costo_marg", 0.0),
                    "attivo": int(st.session_state.get("f_attivo", True)),
                }
                if is_edit:
                    record["id"] = prefill["id"]
                db.upsert_risorsa(record)
                st.success("Risorsa salvata!")
                _refresh()
                
        if is_edit:
            if st.button("🗑️ Elimina risorsa", type="secondary", use_container_width=True):
                db.delete_risorsa(prefill["id"])
                st.success("Risorsa eliminata.")
                _refresh()
            if st.button("✖ Annulla", use_container_width=True):
                _refresh()


# ── decide quale form mostrare ────────────────────────────────────────────────

edit_id = st.session_state.get("edit_risorsa_id")
if edit_id:
    risorsa = db.get_risorsa(int(edit_id))
    if risorsa:
        _form_risorsa(risorsa)
    else:
        st.warning(f"Risorsa ID {edit_id} non trovata.")
        _clear_form_state()
        _form_risorsa()
else:
    _form_risorsa()

# ── filtri ────────────────────────────────────────────────────────────────────

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
        risorse = risorse[risorse["competenze"].apply(lambda c: filter_skill in c)]

    display = risorse.copy()
    def _fmt_competenze(c):
        if isinstance(c, dict):
            return ", ".join(
                f"{s} ({EXPERTISE_LEVELS.get(v, v)})" if v else s
                for s, v in c.items()
            )
        return ", ".join(c) if isinstance(c, list) else str(c)

    display["competenze"] = display["competenze"].apply(_fmt_competenze)
    display["attivo"] = display["attivo"].map({1: "✅", 0: "❌"})
    display = display.rename(columns={
        "id": "ID", "nome": "Nome", "cognome": "Cognome",
        "seniority": "Seniority", "line_manager": "Line Manager",
        "competenze": "Competenze", "costo_giornaliero": "Costo std (€/g)",
        "costo_marginato": "Costo marg (€/g)", "attivo": "Attivo",
    })
    st.dataframe(
        display[["ID","Nome","Cognome","Seniority","Line Manager",
                 "Competenze","Costo std (€/g)","Costo marg (€/g)","Attivo"]],
        use_container_width=True, hide_index=True,
    )

    st.markdown("---")
    st.subheader("Modifica / Elimina")
    sel_id = st.number_input("Inserisci ID risorsa da modificare", min_value=1, step=1, value=1)
    if st.button("✏️ Carica risorsa selezionata"):
        # pulisce il prefill precedente e imposta il nuovo ID → il prossimo render
        # chiamerà _prefill_session_state che scrive tutti i valori nelle chiavi giuste
        st.session_state.pop("_prefill_loaded_id", None)
        st.session_state["edit_risorsa_id"] = int(sel_id)
        st.rerun()
else:
    st.info("Nessuna risorsa presente. Usare il form laterale per aggiungerne una.")
