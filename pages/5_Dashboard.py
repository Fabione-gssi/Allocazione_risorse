"""Dashboard: Gantt, disponibilità mensile, copertura competenze, costi."""

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import database as db
from database import init_db
from esco_skills import ESCO_SKILLS

init_db()

st.set_page_config(page_title="Dashboard", page_icon="📈", layout="wide")
st.title("📈 Dashboard")

# ── load data ─────────────────────────────────────────────────────────────────

risorse_df = db.get_risorse(only_active=True)
progetti_df = db.get_progetti()
alloc_df = db.get_allocazioni()

if alloc_df.empty and progetti_df.empty:
    st.info("Nessun dato disponibile. Inserire progetti, risorse e allocazioni per visualizzare la dashboard.")
    st.stop()

# parse dates
def _pdates(df, col):
    df[col] = pd.to_datetime(df[col], errors="coerce")
    return df

if not progetti_df.empty:
    progetti_df = _pdates(progetti_df, "data_inizio")
    progetti_df = _pdates(progetti_df, "data_fine_prevista")

if not alloc_df.empty:
    alloc_df = _pdates(alloc_df, "data_inizio")
    alloc_df = _pdates(alloc_df, "data_fine")

# ── tab layout ────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📅 Gantt Progetti", "👥 Disponibilità Mensile", "🧩 Copertura Competenze", "💶 Costi", "📊 Riepilogo Allocazioni"]
)

# ============================================================
# TAB 1 – GANTT PROGETTI
# ============================================================
with tab1:
    st.subheader("Gantt dei Progetti")
    if progetti_df.empty:
        st.info("Nessun progetto disponibile.")
    else:
        filter_stati = st.multiselect(
            "Filtra per stato",
            progetti_df["stato"].unique().tolist(),
            default=progetti_df["stato"].unique().tolist(),
            key="gantt_stati",
        )
        gantt_df = progetti_df[progetti_df["stato"].isin(filter_stati)].copy()
        gantt_df = gantt_df.dropna(subset=["data_inizio", "data_fine_prevista"])

        if gantt_df.empty:
            st.info("Nessun progetto con date complete.")
        else:
            color_map = {
                "In offerta": "#aec6cf",
                "In corso": "#4caf50",
                "In pausa": "#ff9800",
                "Completato": "#9e9e9e",
                "Cancellato": "#f44336",
            }
            fig = px.timeline(
                gantt_df,
                x_start="data_inizio",
                x_end="data_fine_prevista",
                y="nome_progetto",
                color="stato",
                color_discrete_map=color_map,
                hover_data=["codice_interno", "referente_interno", "referente_esterno"],
                labels={"nome_progetto": "Progetto", "stato": "Stato"},
                title="Timeline Progetti",
            )
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(height=max(300, 60 * len(gantt_df)), xaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

        # Gantt allocazioni per progetto
        if not alloc_df.empty:
            st.subheader("Gantt Allocazioni per Risorsa")
            alloc_g = alloc_df.dropna(subset=["data_inizio", "data_fine"]).copy()
            alloc_g["label"] = alloc_g["risorsa_nome"] + " — " + alloc_g["nome_progetto"]
            fig2 = px.timeline(
                alloc_g,
                x_start="data_inizio",
                x_end="data_fine",
                y="risorsa_nome",
                color="nome_progetto",
            st.dataframe(cat_df, use_container_width=True, hide_index=True)


# ============================================================
# TAB 2 – DISPONIBILITÀ MENSILE
# ============================================================
with tab2:
    st.subheader("Risorse disponibili e allocate mese per mese")

    if risorse_df.empty:
        st.info("Nessuna risorsa disponibile.")
    else:
        today = date.today()
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            range_start = st.date_input("Da", value=today.replace(day=1), key="disp_start")
        with col_d2:
            range_end = st.date_input(
                "A", value=(today + timedelta(days=365)).replace(day=1), key="disp_end"
            )

        # generate months
        months = []
        cur = range_start.replace(day=1)
        while cur <= range_end:
            months.append(cur)
            if cur.month == 12:
                cur = cur.replace(year=cur.year + 1, month=1)
            else:
                cur = cur.replace(month=cur.month + 1)

        rows_disp = []
        for m in months:
            m_end = (m.replace(month=m.month % 12 + 1, day=1) if m.month < 12
                     else m.replace(year=m.year + 1, month=1, day=1)) - timedelta(days=1)
            total_fte = len(risorse_df) * 100.0
            allocated_fte = 0.0
            if not alloc_df.empty:
                for _, a in alloc_df.iterrows():
                    if pd.isna(a["data_inizio"]) or pd.isna(a["data_fine"]):
                        continue
                    a_start = a["data_inizio"].date() if hasattr(a["data_inizio"], "date") else a["data_inizio"]
                    a_end = a["data_fine"].date() if hasattr(a["data_fine"], "date") else a["data_fine"]
                    if a_start <= m_end and a_end >= m:
                        allocated_fte += a["percentuale_allocazione"]

            rows_disp.append(
                {
                    "Mese": m.strftime("%Y-%m"),
                    "FTE totale (%)": total_fte,
                    "FTE allocato (%)": min(allocated_fte, total_fte),
                    "FTE disponibile (%)": max(0, total_fte - allocated_fte),
                }
            )

        disp_df = pd.DataFrame(rows_disp)
        fig3 = go.Figure()
        fig3.add_bar(
            x=disp_df["Mese"],
            y=disp_df["FTE allocato (%)"],
            name="Allocato",
            marker_color="#ef5350",
        )
        fig3.add_bar(
            x=disp_df["Mese"],
            y=disp_df["FTE disponibile (%)"],
            name="Disponibile",
            marker_color="#66bb6a",
        )
        fig3.update_layout(
            barmode="stack",
            title="FTE aggregato per mese (100% = 1 risorsa a tempo pieno)",
            xaxis_title="Mese",
            yaxis_title="% FTE",
            height=420,
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.dataframe(disp_df, use_container_width=True, hide_index=True)

  
# ============================================================
# TAB 3 – COPERTURA COMPETENZE
# ============================================================
with tab3:
    st.subheader("Copertura delle competenze nel team")

    if risorse_df.empty:
        st.info("Nessuna risorsa disponibile.")
    else:
        skill_counts: dict[str, int] = {}
        for _, r in risorse_df.iterrows():
            competenze = r["competenze"] if isinstance(r["competenze"], list) else []
            for s in competenze:
                skill_counts[s] = skill_counts.get(s, 0) + 1

        if not skill_counts:
            st.info("Nessuna competenza registrata nelle risorse.")
        else:
            skills_ser = (
                pd.Series(skill_counts)
                .sort_values(ascending=False)
            )

            # top 30
            top30 = skills_ser.head(30).reset_index()
            top30.columns = ["Competenza", "N° risorse"]
            fig4 = px.bar(
                top30,
                x="N° risorse",
                y="Competenza",
                orientation="h",
                color="N° risorse",
                color_continuous_scale="Blues",
                title="Top 30 competenze per numero di risorse",
            )
            fig4.update_layout(height=600, yaxis={"autorange": "reversed"})
            st.plotly_chart(fig4, use_container_width=True)

            # heatmap per categoria
            st.subheader("Copertura per categoria ESCO")
            cat_data = []
            for cat, skills in ESCO_SKILLS.items():
                total = len(skills)
                covered = sum(1 for s in skills if s in skill_counts)
                n_people = sum(skill_counts.get(s, 0) for s in skills)
                cat_data.append(
                    {
                        "Categoria": cat,
                        "Skill totali": total,
                        "Skill coperte": covered,
                        "% copertura": round(covered / total * 100, 1),
                        "Tot. persone-skill": n_people,
                    }
                )
            cat_df = pd.DataFrame(cat_data).sort_values("% copertura", ascending=False)
            fig5 = px.bar(
                cat_df,
                x="Categoria",
                y="% copertura",
                color="% copertura",
                color_continuous_scale="RdYlGn",
                title="Copertura % per categoria di competenza",
                range_y=[0, 100],
            )
            fig5.update_layout(height=400)
            st.plotly_chart(fig5, use_container_width=True)
            st.dataframe(cat_df, use_container_width=True, hide_index=True)



# ============================================================
# TAB 4 – COSTI
# ============================================================
with tab4:
    st.subheader("Analisi costi per progetto e risorsa")

    if alloc_df.empty:
        st.info("Nessuna allocazione disponibile.")
    else:
        cost_df = alloc_df.dropna(subset=["data_inizio", "data_fine"]).copy()
        cost_df["giorni_lav"] = (
            ((cost_df["data_fine"] - cost_df["data_inizio"]).dt.days * 5 / 7)
            .clip(lower=0)
            .round(1)
        )
        cost_df["costo_std"] = (
            cost_df["costo_giornaliero"] * cost_df["giorni_lav"] * cost_df["percentuale_allocazione"] / 100
        ).round(0)
        cost_df["costo_marg"] = (
            cost_df["costo_marginato"] * cost_df["giorni_lav"] * cost_df["percentuale_allocazione"] / 100
        ).round(0)

        # per progetto
        by_proj = (
            cost_df.groupby("nome_progetto")[["costo_std", "costo_marg"]]
            .sum()
            .reset_index()
            .sort_values("costo_std", ascending=False)
        )
        fig6 = px.bar(
            by_proj,
            x="nome_progetto",
            y=["costo_std", "costo_marg"],
            barmode="group",
            labels={
                "nome_progetto": "Progetto",
                "value": "Costo (€)",
                "variable": "Tipo",
            },
            color_discrete_map={"costo_std": "#42a5f5", "costo_marg": "#ef5350"},
            title="Costo std vs. marginato per progetto",
        )
        fig6.update_layout(height=400, xaxis_tickangle=-30)
        st.plotly_chart(fig6, use_container_width=True)

        # per risorsa
        by_res = (
            cost_df.groupby("risorsa_nome")[["costo_std", "costo_marg"]]
            .sum()
            .reset_index()
            .sort_values("costo_std", ascending=False)
        )
        fig7 = px.bar(
            by_res,
            x="risorsa_nome",
            y=["costo_std", "costo_marg"],
            barmode="group",
            labels={
                "risorsa_nome": "Risorsa",
                "value": "Costo (€)",
                "variable": "Tipo",
            },
            color_discrete_map={"costo_std": "#42a5f5", "costo_marg": "#ef5350"},
            title="Costo std vs. marginato per risorsa",
        )
        fig7.update_layout(height=400, xaxis_tickangle=-30)
        st.plotly_chart(fig7, use_container_width=True)

        col_c1, col_c2, col_c3 = st.columns(3)
        col_c1.metric("Costo std totale (€)", f"{cost_df['costo_std'].sum():,.0f}")
        col_c2.metric("Costo marginato totale (€)", f"{cost_df['costo_marg'].sum():,.0f}")
        col_c3.metric(
            "Delta margine (%)",
            f"{((cost_df['costo_marg'].sum() / max(cost_df['costo_std'].sum(), 1)) - 1) * 100:.1f}%",
        )

        st.dataframe(
            by_proj.rename(columns={"nome_progetto": "Progetto", "costo_std": "Costo std (€)", "costo_marg": "Costo marg (€)"}),
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# TAB 5 – RIEPILOGO ALLOCAZIONI
# ============================================================
with tab5:
    st.subheader("Matrice risorse × progetti (% FTE)")

    if alloc_df.empty:
        st.info("Nessuna allocazione disponibile.")
    else:
        pivot = alloc_df.pivot_table(
            index="risorsa_nome",
            columns="nome_progetto",
            values="percentuale_allocazione",
            aggfunc="sum",
            fill_value=0,
        )
        st.dataframe(pivot.style.background_gradient(cmap="YlOrRd"), use_container_width=True)
