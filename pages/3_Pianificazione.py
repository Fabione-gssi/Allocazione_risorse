"""Pagina pianificazione: ricerca risorse disponibili e assegnazione a progetto."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

import auth
import database as db
from database import init_db
from esco_skills import ESCO_SKILLS, SENIORITY_LEVELS, all_skills_flat

init_db()

st.set_page_config(page_title="Pianificazione", page_icon="🔍", layout="wide")
st.title("🔍 Pianificazione e Ricerca Risorse")

auth.require_admin()

st.markdown(
    "Cerca le risorse disponibili in un periodo, filtrandole per competenze, "
    "seniority, % FTE minima richiesta e numero richiesto."
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _get_allocation_pct_in_period(
    alloc_df: pd.DataFrame, risorsa_id: int, start: date, end: date
) -> float:
    """Return the total % FTE already allocated for a resource in [start, end]."""
    if alloc_df.empty:
        return 0.0
    r = alloc_df[
        (alloc_df["risorsa_id"] == risorsa_id)
        & (alloc_df["stato"].isin(["Confermata", "Proposta"]))
    ]
    overlap_pct = 0.0
    for _, row in r.iterrows():
        rs = pd.to_datetime(row["data_inizio"]).date()
        re = pd.to_datetime(row["data_fine"]).date()
        if rs <= end and re >= start:
            overlap_pct += row["percentuale_allocazione"]
    return overlap_pct


# ── criteri di ricerca ────────────────────────────────────────────────────────

with st.expander("🔎 Criteri di ricerca", expanded=True):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        search_start = st.date_input("Periodo: dal *", value=date.today())
    with col2:
        search_end = st.date_input(
            "Periodo: al *", value=date.today() + timedelta(days=30)
        )
    with col3:
        min_fte_available = st.slider(
            "% FTE disponibile minima richiesta", 10, 100, 50, 10
        )
    with col4:
        n_risorse = st.number_input(
            "N° risorse necessarie", min_value=1, step=1, value=1
        )

    col5, col6 = st.columns(2)
    with col5:
        required_skills = st.multiselect(
            "Competenze richieste (almeno una)", all_skills_flat()
        )
    with col6:
        required_seniority = st.multiselect(
            "Seniority accettata (lascia vuoto = tutte)", SENIORITY_LEVELS
        )

    search_btn = st.button("🔍 Cerca risorse disponibili", type="primary")

# ── logica di ricerca ─────────────────────────────────────────────────────────

if search_btn or st.session_state.get("last_search"):
    if search_btn:
        st.session_state["last_search"] = {
            "start": search_start,
            "end": search_end,
            "min_fte": min_fte_available,
            "skills": required_skills,
            "seniority": required_seniority,
            "n": n_risorse,
        }

    params = st.session_state["last_search"]
    s_start = params["start"]
    s_end = params["end"]
    s_fte = params["min_fte"]
    s_skills = params["skills"]
    s_seniority = params["seniority"]

    if s_end < s_start:
        st.error("La data fine deve essere successiva alla data inizio.")
        st.stop()

    risorse_df = db.get_risorse(only_active=True)
    alloc_df = db.get_allocazioni()
    if risorse_df.empty:
        st.warning("Nessuna risorsa presente nel sistema.")
        st.stop()

    results = []
    for _, r in risorse_df.iterrows():
        # filtro seniority
        if s_seniority and r["seniority"] not in s_seniority:
            continue

        # filtro competenze: deve avere almeno una delle competenze richieste
        competenze = r["competenze"] if isinstance(r["competenze"], list) else []
        if s_skills and not any(sk in competenze for sk in s_skills):
            continue

        # calcola FTE occupato nel periodo
        occupied = _get_allocation_pct_in_period(alloc_df, r["id"], s_start, s_end)
        available = max(0.0, 100.0 - occupied)

        if available < s_fte:
            continue

        skill_match = [sk for sk in s_skills if sk in competenze] if s_skills else []
        results.append(
            {
                "id": r["id"],
                "Cognome": r["cognome"],
                "Nome": r["nome"],
                "Seniority": r["seniority"],
                "Line Manager": r["line_manager"],
                "Competenze corrispondenti": ", ".join(skill_match),
                "% FTE occupato": round(occupied, 1),
                "% FTE disponibile": round(available, 1),
                "Costo std (€/g)": r["costo_giornaliero"],
                "Costo marg (€/g)": r["costo_marginato"],
            }
        )

    st.divider()
    st.subheader(f"Risultati: {len(results)} risorsa/e trovata/e")

    if results:
        res_df = pd.DataFrame(results).sort_values("% FTE disponibile", ascending=False)
        st.dataframe(res_df.drop(columns=["id"]), use_container_width=True, hide_index=True)

        # ── assegnazione rapida ───────────────────────────────────────────────

        st.markdown("---")
        st.subheader("⚡ Assegnazione rapida")

        progetti_df = db.get_progetti()
        if progetti_df.empty:
            st.info("Nessun progetto disponibile per l'assegnazione.")
        else:
            progetti_map = {
                f"[{p['codice_interno']}] {p['nome_progetto']}": p["id"]
                for _, p in progetti_df.iterrows()
            }
            risorse_ids_available = res_df["id"].tolist()
            risorse_label_map = {
                f"{r['Cognome']} {r['Nome']} (FTE lib: {r['% FTE disponibile']}%)": r["id"]
                for r in results
            }

            with st.form("form_assign"):
                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    sel_risorse_keys = st.multiselect(
                        "Risorse da assegnare *",
                        list(risorse_label_map.keys()),
                    )
                with col_a2:
                    sel_progetto_key = st.selectbox("Progetto *", list(progetti_map.keys()))

                col_a3, col_a4, col_a5 = st.columns(3)
                with col_a3:
                    assign_start = st.date_input("Dal *", value=s_start)
                with col_a4:
                    assign_end = st.date_input("Al *", value=s_end)
                with col_a5:
                    assign_pct = st.slider("% FTE da assegnare", 5, 100, int(s_fte), 5)

                note_assign = st.text_input("Note (opzionale)")

                assign_btn = st.form_submit_button("✅ Assegna risorse selezionate", type="primary")
                if assign_btn:
                    if not sel_risorse_keys:
                        st.error("Seleziona almeno una risorsa.")
                    elif assign_end < assign_start:
                        st.error("La data fine deve essere successiva alla data inizio.")
                    else:
                        progetto_id = progetti_map[sel_progetto_key]
                        saved = 0
                        for key in sel_risorse_keys:
                            risorsa_id = risorse_label_map[key]
                            occupied = _get_allocation_pct_in_period(
                                alloc_df, risorsa_id, assign_start, assign_end
                            )
                            if occupied + assign_pct > 100:
                                st.warning(
                                    f"⚠️ {key}: l'allocazione supererebbe il 100% FTE nel periodo indicato."
                                )
                                continue
                            db.upsert_allocazione(
                                {
                                    "risorsa_id": risorsa_id,
                                    "progetto_id": progetto_id,
                                    "data_inizio": assign_start.isoformat(),
                                    "data_fine": assign_end.isoformat(),
                                    "percentuale_allocazione": assign_pct,
                                    "stato": "Confermata",
                                    "note": note_assign,
                                }
                            )
                            saved += 1
                        if saved:
                            st.success(f"{saved} allocazione/i create con successo!")
                            st.session_state.pop("last_search", None)
                            st.rerun()
    else:
        st.info("Nessuna risorsa soddisfa i criteri selezionati nel periodo indicato.")
      
