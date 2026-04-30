"""Pagina import / export Excel."""

import io
from datetime import date

import auth
import pandas as pd
import streamlit as st

import database as db
from database import init_db

init_db()


def _fmt_sheet(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame) -> None:
    """Auto-width columns in xlsxwriter."""
    ws = writer.sheets[sheet_name]
    workbook = writer.book
    header_fmt = workbook.add_format(
        {"bold": True, "bg_color": "#1e3a5f", "font_color": "white", "border": 1}
    )
    for col_num, col_name in enumerate(df.columns):
        ws.write(0, col_num, col_name, header_fmt)
        col_width = max(len(str(col_name)) + 2, 12)
        if not df.empty:
            col_width = max(col_width, df[col_name].astype(str).str.len().max() + 2)
        ws.set_column(col_num, col_num, min(col_width, 50))


st.set_page_config(page_title="Import / Export", page_icon="⬆️", layout="wide")
st.title("⬆️ Import / Export")
auth.require_admin()

tab_import, tab_export, tab_template = st.tabs(
    ["📥 Upload Excel", "📤 Download Excel", "📋 Template Excel"]
)

# ============================================================
# TAB IMPORT
# ============================================================
with tab_import:
    st.markdown(
        "Carica un file Excel per importare **risorse** o **progetti** in blocco. "
        "Scarica prima il template nella scheda *Template* per conoscere le colonne attese."
    )

    col_l, col_r = st.columns(2)

    # ── import risorse ────────────────────────────────────────────────────────
    with col_l:
        st.subheader("Importa Risorse")
        file_risorse = st.file_uploader(
            "File Excel risorse (.xlsx)", type=["xlsx"], key="ul_risorse"
        )
        if file_risorse:
            try:
                df_r = pd.read_excel(file_risorse, dtype=str)
                df_r.columns = df_r.columns.str.strip().str.lower().str.replace(" ", "_")
                st.write("Anteprima (prime 5 righe):")
                st.dataframe(df_r.head(), use_container_width=True)

                required_cols = {"nome", "cognome", "seniority"}
                missing = required_cols - set(df_r.columns)
                if missing:
                    st.error(f"Colonne mancanti: {', '.join(missing)}")
                else:
                    if st.button("✅ Importa risorse", type="primary"):
                        n, errors = db.bulk_insert_risorse(df_r)
                        st.success(f"{n} risorsa/e importata/e con successo.")
                        if errors:
                            st.warning("Errori su alcune righe:")
                            for e in errors:
                                st.text(e)
            except Exception as exc:
                st.error(f"Errore nella lettura del file: {exc}")

    # ── import progetti ───────────────────────────────────────────────────────
    with col_r:
        st.subheader("Importa Progetti")
        file_progetti = st.file_uploader(
            "File Excel progetti (.xlsx)", type=["xlsx"], key="ul_progetti"
        )
        if file_progetti:
            try:
                df_p = pd.read_excel(file_progetti, dtype=str)
                df_p.columns = df_p.columns.str.strip().str.lower().str.replace(" ", "_")
                st.write("Anteprima (prime 5 righe):")
                st.dataframe(df_p.head(), use_container_width=True)

                required_cols = {"nome_progetto"}
                missing = required_cols - set(df_p.columns)
                if missing:
                    st.error(f"Colonne mancanti: {', '.join(missing)}")
                else:
                    if st.button("✅ Importa progetti", type="primary"):
                        n, errors = db.bulk_insert_progetti(df_p)
                        st.success(f"{n} progetto/i importato/i con successo.")
                        if errors:
                            st.warning("Errori su alcune righe:")
                            for e in errors:
                                st.text(e)

            except Exception as exc:
                st.error(f"Errore nella lettura del file: {exc}")

# ============================================================
# TAB EXPORT
# ============================================================
with tab_export:
    st.subheader("Scarica report Excel completo")
    st.markdown(
        "Il file conterrà tre fogli: **Risorse**, **Progetti**, **Allocazioni** "
        "con tutti i dettagli disponibili."
    )

    if st.button("🔄 Genera report Excel", type="primary"):
        risorse_df = db.get_risorse()
        progetti_df = db.get_progetti()
        alloc_df = db.get_allocazioni()

        # arricchisci allocazioni con costi calcolati
        if not alloc_df.empty:
            alloc_df["data_inizio_dt"] = pd.to_datetime(alloc_df["data_inizio"], errors="coerce")
            alloc_df["data_fine_dt"] = pd.to_datetime(alloc_df["data_fine"], errors="coerce")
            alloc_df["giorni_lavorativi"] = (
                ((alloc_df["data_fine_dt"] - alloc_df["data_inizio_dt"]).dt.days * 5 / 7)
                .clip(lower=0)
                .round(0)
            )
            alloc_df["costo_std_totale"] = (
                alloc_df["costo_giornaliero"]
                * alloc_df["giorni_lavorativi"]
                * alloc_df["percentuale_allocazione"]
                / 100
            ).round(2)
            alloc_df["costo_marg_totale"] = (
                alloc_df["costo_marginato"]
                * alloc_df["giorni_lavorativi"]
                * alloc_df["percentuale_allocazione"]
                / 100
            ).round(2)

        # flatten competenze
        if not risorse_df.empty:
            risorse_df["competenze"] = risorse_df["competenze"].apply(
                lambda c: "; ".join(
                    f"{s} ({v})" for s, v in c.items()
                ) if isinstance(c, dict) else ("; ".join(c) if isinstance(c, list) else c)
            )

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            # RISORSE
            if not risorse_df.empty:
                risorse_export = risorse_df.drop(
                    columns=[c for c in ["created_at", "updated_at"] if c in risorse_df.columns]
                )
                risorse_export.to_excel(writer, sheet_name="Risorse", index=False)
                _fmt_sheet(writer, "Risorse", risorse_export)

            # PROGETTI
            if not progetti_df.empty:
                progetti_export = progetti_df.drop(
                    columns=[c for c in ["created_at", "updated_at"] if c in progetti_df.columns]
                )
                progetti_export.to_excel(writer, sheet_name="Progetti", index=False)
                _fmt_sheet(writer, "Progetti", progetti_export)

            # ALLOCAZIONI
            if not alloc_df.empty:
                alloc_export = alloc_df[
                    [
                        "id", "risorsa_nome", "seniority", "nome_progetto",
                        "codice_interno", "codice_esterno",
                        "data_inizio", "data_fine", "percentuale_allocazione",
                        "stato", "giorni_lavorativi",
                        "costo_std_totale", "costo_marg_totale", "note",
                    ]
                ].copy()
                alloc_export.columns = [
                    "ID", "Risorsa", "Seniority", "Progetto",
                    "Cod. Interno", "Cod. Esterno",
                    "Data Inizio", "Data Fine", "% FTE",
                    "Stato", "Giorni Lavorativi",
                    "Costo Std Totale (€)", "Costo Marg Totale (€)", "Note",
                ]
                alloc_export.to_excel(writer, sheet_name="Allocazioni", index=False)
                _fmt_sheet(writer, "Allocazioni", alloc_export)

        output.seek(0)
        st.download_button(
            label="⬇️ Scarica report_allocazioni.xlsx",
            data=output,
            file_name=f"report_allocazioni_{date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ============================================================
# TAB TEMPLATE
# ============================================================
with tab_template:
    st.subheader("Template Excel per importazione")
    st.markdown("Scarica i template precompilati con la struttura delle colonne attese.")

    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.markdown("**Template Risorse**")
        template_r = pd.DataFrame(
            columns=[
                "nome", "cognome", "seniority", "line_manager",
                "competenze", "costo_giornaliero", "costo_marginato",
            ]
        )
        # esempio
        template_r.loc[0] = [
            "Mario", "Rossi", "Senior", "Anna Bianchi",
            "Python; Machine learning; SQL avanzato",
            500, 650,
        ]
        buf_r = io.BytesIO()
        with pd.ExcelWriter(buf_r, engine="xlsxwriter") as wr:
            template_r.to_excel(wr, sheet_name="Risorse", index=False)
            _fmt_sheet(wr, "Risorse", template_r)
        buf_r.seek(0)
        st.download_button(
            "⬇️ template_risorse.xlsx",
            buf_r,
            "template_risorse.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.dataframe(template_r, use_container_width=True, hide_index=True)
        st.caption(
            "**competenze**: lista separata da `;`  |  "
            "**seniority**: Junior / Mid / Senior / Principal / Lead"
        )

    with col_t2:
        st.markdown("**Template Progetti**")
        template_p = pd.DataFrame(
            columns=[
                "codice_interno", "codice_esterno", "nome_progetto",
                "referente_interno", "referente_esterno",
                "data_inizio", "data_fine_prevista", "stato", "note",
            ]
        )
        template_p.loc[0] = [
            "INT-001", "EXT-2024-01", "Progetto Alpha",
            "Anna Bianchi", "Cliente SpA",
            "2024-01-01", "2024-12-31", "In corso", "",
        ]
        buf_p = io.BytesIO()
        with pd.ExcelWriter(buf_p, engine="xlsxwriter") as wr:
            template_p.to_excel(wr, sheet_name="Progetti", index=False)
            _fmt_sheet(wr, "Progetti", template_p)
        buf_p.seek(0)
        st.download_button(
            "⬇️ template_progetti.xlsx",
            buf_p,
            "template_progetti.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.dataframe(template_p, use_container_width=True, hide_index=True)
        st.caption(
            "**stato**: In offerta / In corso / In pausa / Completato / Cancellato  |  "
            "**date**: formato YYYY-MM-DD"
        )
