"""PostgreSQL / Supabase database layer — drop-in replacement for SQLite."""

import contextlib
import json

import pandas as pd

import psycopg2
import psycopg2.extras
import streamlit as st

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _conn():
    """Open a connection, commit on success, rollback on error, always close."""
    conn = psycopg2.connect(
        st.secrets["supabase"]["connection_string"],
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema init
# ---------------------------------------------------------------------------

def init_db() -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS risorse (
                    id                  BIGSERIAL PRIMARY KEY,
                    nome                TEXT    NOT NULL,
                    cognome             TEXT    NOT NULL,
                    seniority           TEXT    NOT NULL,
                    line_manager        TEXT    DEFAULT '',
                    competenze          TEXT    DEFAULT '[]',
                    costo_giornaliero   REAL    DEFAULT 0.0,
                    costo_marginato     REAL    DEFAULT 0.0,
                    attivo              INTEGER DEFAULT 1,
                    created_at          TIMESTAMPTZ DEFAULT NOW(),
                    updated_at          TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS progetti (
                    id                  BIGSERIAL PRIMARY KEY,
                    codice_esterno      TEXT    DEFAULT '',
                    codice_interno      TEXT    DEFAULT '',
                    nome_progetto       TEXT    NOT NULL,
                    referente_interno   TEXT    DEFAULT '',
                    referente_esterno   TEXT    DEFAULT '',
                    data_inizio         TEXT    DEFAULT '',
                    data_fine_prevista  TEXT    DEFAULT '',
                    stato               TEXT    DEFAULT 'In corso',
                    note                TEXT    DEFAULT '',
                    created_at          TIMESTAMPTZ DEFAULT NOW(),
                    updated_at          TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS allocazioni (
                    id                      BIGSERIAL PRIMARY KEY,
                    risorsa_id              BIGINT  NOT NULL,
                    progetto_id             BIGINT  NOT NULL,
                    data_inizio             TEXT    NOT NULL,
                    data_fine               TEXT    NOT NULL,
                    percentuale_allocazione REAL    NOT NULL DEFAULT 100.0,
                    stato                   TEXT    DEFAULT 'Confermata',
                    note                    TEXT    DEFAULT '',
                    created_at              TIMESTAMPTZ DEFAULT NOW(),
                    updated_at              TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (risorsa_id)  REFERENCES risorse(id)  ON DELETE CASCADE,
                    FOREIGN KEY (progetto_id) REFERENCES progetti(id) ON DELETE CASCADE
                );
                """
            )


# ---------------------------------------------------------------------------

def get_risorse(only_active: bool = False) -> pd.DataFrame:
    with _conn() as conn:
        with conn.cursor() as cur:
            q = "SELECT * FROM risorse"
            if only_active:
                q += " WHERE attivo = 1"
            q += " ORDER BY cognome, nome"
            cur.execute(q)
            rows = cur.fetchall()
    df = _rows_to_df(rows)
    if not df.empty:
        df["competenze"] = df["competenze"].apply()

def get_risorsa(risorsa_id: int) -> dict | None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM risorse WHERE id = %s", (risorsa_id,))
            row = cur.fetchone()
    if row is None:
        return None
    d = dict(row)
def upsert_risorsa(data: dict) -> int:
    competenze = json.dumps(data.get("competenze", []))
    with _conn() as conn:
        with conn.cursor() as cur:
            if data.get("id"):
                cur.execute(
                    """UPDATE risorse SET
                        nome=%s, cognome=%s, seniority=%s, line_manager=%s,
                        competenze=%s, costo_giornaliero=%s, costo_marginato=%s,
                        attivo=%s, updated_at=NOW()
                       WHERE id=%s""",
                    (
                        data["nome"], data["cognome"], data["seniority"],
                        data.get("line_manager", ""), competenze,
                        data.get("costo_giornaliero", 0), data.get("costo_marginato", 0),
                        int(data.get("attivo", 1)), data["id"],
                    ),
                )
                return data["id"]
            cur.execute(
                """INSERT INTO risorse
                   (nome, cognome, seniority, line_manager, competenze,
                    costo_giornaliero, costo_marginato, attivo)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    data["nome"], data["cognome"], data["seniority"],
                    data.get("line_manager", ""), competenze,
                    data.get("costo_giornaliero", 0), data.get("costo_marginato", 0),
                    int(data.get("attivo", 1)),
                ),
            )
            return cur.fetchone()["id"]


def delete_risorsa(risorsa_id: int) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM risorse WHERE id = %s", (risorsa_id,))


# ---------------------------------------------------------------------------

def get_progetti() -> pd.DataFrame:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM progetti ORDER BY data_inizio DESC, nome_progetto"
            )
            rows = cur.fetchall()
    return _rows_to_df(rows)


def get_progetto(progetto_id: int) -> dict | None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM progetti WHERE id = %s", (progetto_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def upsert_progetto(data: dict) -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            if data.get("id"):
                cur.execute(
                    """UPDATE progetti SET
                        codice_esterno=%s, codice_interno=%s, nome_progetto=%s,
                        referente_interno=%s, referente_esterno=%s,
                        data_inizio=%s, data_fine_prevista=%s, stato=%s, note=%s,
                        updated_at=NOW()
                       WHERE id=%s""",
                    (
                        data.get("codice_esterno", ""), data.get("codice_interno", ""),
                        data["nome_progetto"],
                        data.get("referente_interno", ""), data.get("referente_esterno", ""),
                        data.get("data_inizio", ""), data.get("data_fine_prevista", ""),
                        data.get("stato", "In corso"), data.get("note", ""),
                        data["id"],
                    ),
                )
                return data["id"]
            cur.execute(
                """INSERT INTO progetti
                   (codice_esterno, codice_interno, nome_progetto,
                    referente_interno, referente_esterno,
                    data_inizio, data_fine_prevista, stato, note)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    data.get("codice_esterno", ""), data.get("codice_interno", ""),
                    data["nome_progetto"],
                    data.get("referente_interno", ""), data.get("referente_esterno", ""),
                    data.get("data_inizio", ""), data.get("data_fine_prevista", ""),
                    data.get("stato", "In corso"), data.get("note", ""),
                ),
            )
            return cur.fetchone()["id"]


def delete_progetto(progetto_id: int) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM progetti WHERE id = %s", (progetto_id,))


# ---------------------------------------------------------------------------

def get_allocazioni() -> pd.DataFrame:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.*,
                       r.nome || ' ' || r.cognome AS risorsa_nome,
                       r.seniority,
                       r.costo_giornaliero,
                       r.costo_marginato,
                       p.nome_progetto,
                       p.codice_interno,
                       p.codice_esterno,
                       p.stato AS progetto_stato
                FROM allocazioni a
                JOIN risorse  r ON r.id = a.risorsa_id
                JOIN progetti p ON p.id = a.progetto_id
                ORDER BY a.data_inizio DESC
                """
            )
            rows = cur.fetchall()
    return _rows_to_df(rows)


def get_allocazioni_risorsa(risorsa_id: int) -> pd.DataFrame:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.*, p.nome_progetto, p.stato AS progetto_stato
                FROM allocazioni a
                JOIN progetti p ON p.id = a.progetto_id
                WHERE a.risorsa_id = %s
                ORDER BY a.data_inizio
                """,
                (risorsa_id,),
            )
            rows = cur.fetchall()
    return _rows_to_df(rows)


def upsert_allocazione(data: dict) -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            if data.get("id"):
                cur.execute(
                    """UPDATE allocazioni SET
                        risorsa_id=%s, progetto_id=%s,
                        data_inizio=%s, data_fine=%s,
                        percentuale_allocazione=%s, stato=%s, note=%s,
                        updated_at=NOW()
                       WHERE id=%s""",
                    (
                        data["risorsa_id"], data["progetto_id"],
                        data["data_inizio"], data["data_fine"],
                        data["percentuale_allocazione"],
                        data.get("stato", "Confermata"), data.get("note", ""),
                        data["id"],
                    ),
                )
                return data["id"]
            cur.execute(
                """INSERT INTO allocazioni
                   (risorsa_id, progetto_id, data_inizio, data_fine,
                    percentuale_allocazione, stato, note)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    data["risorsa_id"], data["progetto_id"],
                    data["data_inizio"], data["data_fine"],
                    data["percentuale_allocazione"],
                    data.get("stato", "Confermata"), data.get("note", ""),
                ),
            )
            return cur.fetchone()["id"]


def delete_allocazione(allocazione_id: int) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM allocazioni WHERE id = %s", (allocazione_id,))


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

def bulk_insert_risorse(df: pd.DataFrame) -> tuple[int, list[str]]:
    inserted, errors = 0, []
    for i, row in df.iterrows():
        try:
            competenze = []
            if "competenze" in row and pd.notna(row["competenze"]):
                competenze = [s.strip() for s in str(row["competenze"]).split(";") if s.strip()]
            upsert_risorsa(
                {
                    "nome": str(row.get("nome", "")).strip(),






        
