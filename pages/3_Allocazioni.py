"""Pagina gestione allocazioni."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

import database as db
from database import init_db
from esco_skills import ALLOCATION_STATUS_OPTIONS

init_db()

st.set_page_config(page_title="Allocazioni", page_icon="🔗", layout="wide")
st.title("🔗 Allocazioni Risorse ↔ Progetti")


# ── helpers ───────────────────────────────────────────────────────────────────

def _working_days(start: date, end: date) -> int:
    """Giorni lavorativi (lun-ven) nel periodo [start, end] inclusi."""
    if end < start:
        return 0
    return int(np.busday_count(start, end + timedelta(days=1)))


def _refresh():
    st.session_state.pop("edit_alloc_id", None)
    st.rerun()


def _parse_date(val) -> date:
    if not val or str(val) == "nan":
        return date.today()
    try:
        return date.fromisoformat(str(val)[:10])
    except Exception:
        return date.today()


# ── form sidebar: nuova / modifica singola allocazione ────────────────────────

def _form_allocazione(prefill: dict | None = None):
    is_edit = prefill is not None and prefill.get("id")

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
        st.subheader("✏️ Modifica" if is_edit else "➕ Nuova allocazione")
        with st.form("form_alloc", clear_on_submit=True):

            # risorsa e progetto
            default_r = (
                next((k for k, v in risorse_map.items() if v == prefill.get("risorsa_id")),
                     list(risorse_map.keys())[0])
                if is_edit else list(risorse_map.keys())[0]
            )
            default_p = (
                next((k for k, v in progetti_map.items() if v == prefill.get("progetto_id")),
                     list(progetti_map.keys())[0])
                if is_edit else list(progetti_map.keys())[0]
            )
            risorsa_key = st.selectbox("Risorsa *", list(risorse_map.keys()),
                                       index=list(risorse_map.keys()).index(default_r))
            progetto_key = st.selectbox("Progetto *", list(progetti_map.keys()),
                                        index=list(progetti_map.keys()).index(default_p))

            # date
            data_inizio = st.date_input(
                "Data inizio *",
                value=_parse_date(prefill.get("data_inizio")) if is_edit else date.today(),
            )
            data_fine = st.date_input(
                "Data fine *",
                value=_parse_date(prefill.get("data_fine")) if is_edit else date.today(),
            )

            # calcola giorni lavorativi disponibili
            gg_disp = _working_days(data_inizio, data_fine)
            st.caption(f"📅 Giorni lavorativi nel periodo: **{gg_disp}**")

            # modalità inserimento FTE
            modalita = st.radio(
                "Inserisci la % FTE come:",
                ["Percentuale diretta", "Giorni lavorati"],
                horizontal=True,
            )

            if modalita == "Percentuale diretta":
                perc = st.slider(
                    "% Allocazione FTE",
                    min_value=5, max_value=100, step=5,
                    value=int(prefill.get("percentuale_allocazione", 100)) if is_edit else 100,
                )
                gg_lavorati = None
            else:
                gg_lavorati = st.number_input(
                    "Giorni lavorati",
                    min_value=1,
                    max_value=max(gg_disp, 1),
                    step=1,
                    value=min(gg_disp, max(1, round(
                        gg_disp * (prefill.get("percentuale_allocazione", 100) / 100)
                    ))) if is_edit else gg_disp,
                )
                perc = None
                if gg_disp > 0:
                    perc_calc = round(gg_lavorati / gg_disp * 100)
                    st.caption(f"→ % FTE calcolata: **{perc_calc}%**")

            stato = st.selectbox(
                "Stato allocazione",
                ALLOCATION_STATUS_OPTIONS,
                index=ALLOCATION_STATUS_OPTIONS.index(prefill["stato"])
                if is_edit and prefill.get("stato") in ALLOCATION_STATUS_OPTIONS else 0,
            )
            note = st.text_area("Note", value=prefill.get("note", "") if is_edit else "", height=60)

            submitted = st.form_submit_button("💾 Salva")
            if submitted:
                if data_fine < data_inizio:
                    st.error("La data fine deve essere successiva alla data inizio.")
                else:
                    # calcola FTE finale
                    if modalita == "Giorni lavorati":
                        fte_finale = round(gg_lavorati / max(gg_disp, 1) * 100)
                        fte_finale = max(1, min(100, fte_finale))
                    else:
                        fte_finale = perc

                    record = {
                        "risorsa_id": risorse_map[risorsa_key],
                        "progetto_id": progetti_map[progetto_key],
                        "data_inizio": data_inizio.isoformat(),
                        "data_fine": data_fine.isoformat(),
                        "percentuale_allocazione": fte_finale,
                        "stato": stato,
                        "note": note.strip(),
                    }
                    if is_edit:
                        record["id"] = prefill["id"]
                    db.upsert_allocazione(record)
                    st.success(f"Allocazione salvata! (FTE: {fte_finale}%)")
                    _refresh()

        if is_edit:
            if st.button("🗑️ Elimina", type="secondary"):
                db.delete_allocazione(prefill["id"])
                st.success("Eliminata.")
                _refresh()
            if st.button("✖ Annulla"):
                _refresh()


# ── load prefill se in edit mode ──────────────────────────────────────────────

edit_id = st.session_state.get("edit_alloc_id")
prefill = None
if edit_id:
    alloc_df = db.get_allocazioni()
    if not alloc_df.empty:
        rows = alloc_df[alloc_df["id"] == edit_id]
        if not rows.empty:
            prefill = rows.iloc[0].to_dict()

_form_allocazione(prefill)

# ── ALLOCAZIONE RAPIDA MULTIPLA ───────────────────────────────────────────────

st.divider()
st.subheader("⚡ Allocazione rapida multipla")
st.markdown(
    "Seleziona un progetto e le risorse da allocare, imposta le date comuni "
    "e personalizza FTE/giorni per ogni risorsa nella tabella."
)

risorse_df = db.get_risorse(only_active=True)
progetti_df = db.get_progetti()

if risorse_df.empty or progetti_df.empty:
    st.info("Inserisci prima risorse e progetti.")
else:
    col_q1, col_q2 = st.columns([2, 2])
    with col_q1:
        progetto_opts = {
            f"[{p['codice_interno']}] {p['nome_progetto']}": p["id"]
            for _, p in progetti_df.iterrows()
        }
        sel_progetto_label = st.selectbox("Progetto *", list(progetto_opts.keys()),
                                          key="quick_progetto")
        sel_progetto_id = progetto_opts[sel_progetto_label]

    with col_q2:
        risorsa_opts = {
            f"{r['cognome']} {r['nome']}": r["id"]
            for _, r in risorse_df.iterrows()
        }
        sel_risorse_labels = st.multiselect(
            "Risorse da allocare *",
            list(risorsa_opts.keys()),
            key="quick_risorse",
        )

    col_q3, col_q4, col_q5 = st.columns([2, 2, 2])
    with col_q3:
        quick_inizio = st.date_input("Data inizio comune", value=date.today(), key="quick_inizio")
    with col_q4:
        quick_fine = st.date_input("Data fine comune",
                                   value=date.today() + timedelta(days=30), key="quick_fine")
    with col_q5:
        quick_modalita = st.radio("FTE come:", ["% FTE", "Giorni lavorati"],
                                  horizontal=True, key="quick_modalita")

    gg_comuni = _working_days(quick_inizio, quick_fine)
    st.caption(f"📅 Giorni lavorativi nel periodo comune: **{gg_comuni}**")

    if sel_risorse_labels and quick_fine >= quick_inizio:
        # costruisce il dataframe editabile
        rows_edit = []
        for label in sel_risorse_labels:
            rid = risorsa_opts[label]
            rows_edit.append({
                "Risorsa": label,
                "Data inizio": quick_inizio.isoformat(),
                "Data fine": quick_fine.isoformat(),
                "% FTE" if quick_modalita == "% FTE" else "Giorni lavorati":
                    100 if quick_modalita == "% FTE" else gg_comuni,
                "Stato": ALLOCATION_STATUS_OPTIONS[0],
                "Note": "",
                "_risorsa_id": rid,
            })

        col_label = "% FTE" if quick_modalita == "% FTE" else "Giorni lavorati"
        col_max = 100 if quick_modalita == "% FTE" else max(gg_comuni, 1)

        edited = st.data_editor(
            pd.DataFrame(rows_edit),
            column_config={
                "Risorsa": st.column_config.TextColumn(disabled=True),
                "Data inizio": st.column_config.TextColumn(),
                "Data fine": st.column_config.TextColumn(),
                col_label: st.column_config.NumberColumn(
                    min_value=1, max_value=col_max, step=1 if quick_modalita == "Giorni lavorati" else 5,
                ),
                "Stato": st.column_config.SelectboxColumn(options=ALLOCATION_STATUS_OPTIONS),
                "Note": st.column_config.TextColumn(),
                "_risorsa_id": None,  # nasconde la colonna ID
            },
            hide_index=True,
            use_container_width=True,
            key="quick_editor",
        )

        if st.button("✅ Crea allocazioni", type="primary"):
            saved, warnings_list = 0, []
            for _, row in edited.iterrows():
                try:
                    d_ini = date.fromisoformat(str(row["Data inizio"])[:10])
                    d_fin = date.fromisoformat(str(row["Data fine"])[:10])
                    if d_fin < d_ini:
                        warnings_list.append(f"{row['Risorsa']}: data fine precedente a data inizio, ignorata.")
                        continue

                    if quick_modalita == "Giorni lavorati":
                        gg_disp = _working_days(d_ini, d_fin)
                        gg_lav = int(row["Giorni lavorati"])
                        fte = max(1, min(100, round(gg_lav / max(gg_disp, 1) * 100)))
                    else:
                        fte = int(row["% FTE"])

                    db.upsert_allocazione({
                        "risorsa_id": int(row["_risorsa_id"]),
                        "progetto_id": sel_progetto_id,
                        "data_inizio": d_ini.isoformat(),
                        "data_fine": d_fin.isoformat(),
                        "percentuale_allocazione": fte,
                        "stato": row["Stato"],
                        "note": str(row["Note"]),
                    })
                    saved += 1
                except Exception as exc:
                    warnings_list.append(f"{row['Risorsa']}: {exc}")

            if saved:
                st.success(f"{saved} allocazione/i create con successo!")
            for w in warnings_list:
                st.warning(w)
            if saved:
                st.rerun()
    elif sel_risorse_labels and quick_fine < quick_inizio:
        st.error("La data fine deve essere successiva alla data inizio.")

# ── tabella allocazioni ───────────────────────────────────────────────────────

st.divider()
st.subheader("📋 Elenco allocazioni")

col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
with col_f1:
    risorsa_opts_all = ["— tutte —"] + (
        [f"{r['cognome']} {r['nome']}" for _, r in risorse_df.iterrows()]
        if not risorse_df.empty else []
    )
    filter_risorsa = st.selectbox("Filtra risorsa", risorsa_opts_all)
with col_f2:
    progetto_opts_all = ["— tutti —"] + (
        [p["nome_progetto"] for _, p in progetti_df.iterrows()]
        if not progetti_df.empty else []
    )
    filter_progetto = st.selectbox("Filtra progetto", progetto_opts_all)
with col_f3:
    filter_stato = st.multiselect("Filtra stato", ALLOCATION_STATUS_OPTIONS)

alloc_df = db.get_allocazioni()

if not alloc_df.empty:
    if filter_risorsa != "— tutte —":
        alloc_df = alloc_df[alloc_df["risorsa_nome"] == filter_risorsa]
    if filter_progetto != "— tutti —":
        alloc_df = alloc_df[alloc_df["nome_progetto"] == filter_progetto]
    if filter_stato:
        alloc_df = alloc_df[alloc_df["stato"].isin(filter_stato)]

    alloc_df["_d_ini"] = pd.to_datetime(alloc_df["data_inizio"], errors="coerce")
    alloc_df["_d_fin"] = pd.to_datetime(alloc_df["data_fine"], errors="coerce")
    alloc_df["giorni_lav"] = alloc_df.apply(
        lambda r: _working_days(r["_d_ini"].date(), r["_d_fin"].date())
        if pd.notna(r["_d_ini"]) and pd.notna(r["_d_fin"]) else 0,
        axis=1,
    )
    alloc_df["gg_allocati"] = (
        alloc_df["giorni_lav"] * alloc_df["percentuale_allocazione"] / 100
    ).round(1)
    alloc_df["costo_std"] = (
        alloc_df["costo_giornaliero"] * alloc_df["gg_allocati"]
    ).round(0)
    alloc_df["costo_marg"] = (
        alloc_df["costo_marginato"] * alloc_df["gg_allocati"]
    ).round(0)

    display = alloc_df.rename(columns={
        "id": "ID", "risorsa_nome": "Risorsa", "seniority": "Seniority",
        "nome_progetto": "Progetto", "codice_interno": "Cod. Int.",
        "data_inizio": "Inizio", "data_fine": "Fine",
        "percentuale_allocazione": "% FTE", "stato": "Stato",
        "giorni_lav": "Gg Disp.", "gg_allocati": "Gg Allocati",
        "costo_std": "Costo Std (€)", "costo_marg": "Costo Marg (€)", "note": "Note",
    })
    show_cols = ["ID", "Risorsa", "Seniority", "Progetto", "Cod. Int.",
                 "Inizio", "Fine", "% FTE", "Stato",
                 "Gg Disp.", "Gg Allocati", "Costo Std (€)", "Costo Marg (€)", "Note"]
    st.dataframe(display[show_cols], use_container_width=True, hide_index=True)

    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("Righe visualizzate", len(alloc_df))
    col_t2.metric("Costo std totale (€)", f"{alloc_df['costo_std'].sum():,.0f}")
    col_t3.metric("Costo marginato totale (€)", f"{alloc_df['costo_marg'].sum():,.0f}")

    st.markdown("---")
    sel_id = st.number_input("ID allocazione da modificare", min_value=1, step=1, value=1)
    if st.button("✏️ Carica allocazione selezionata"):
        st.session_state["edit_alloc_id"] = int(sel_id)
        st.rerun()
else:
    st.info("Nessuna allocazione presente.")
