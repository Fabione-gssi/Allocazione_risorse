"""SQLite database layer — single source of truth for all CRUD operations."""

import json
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "allocazioni.db"


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS risorse (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                nome                TEXT    NOT NULL,
                cognome             TEXT    NOT NULL,
                seniority           TEXT    NOT NULL,
                line_manager        TEXT    DEFAULT '',
                competenze          TEXT    DEFAULT '[]',
                costo_giornaliero   REAL    DEFAULT 0.0,
                costo_marginato     REAL    DEFAULT 0.0,
                attivo              INTEGER DEFAULT 1,
                created_at          TEXT    DEFAULT (datetime('now')),
                updated_at          TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS progetti (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                codice_esterno      TEXT    DEFAULT '',
                codice_interno      TEXT    DEFAULT '',
                nome_progetto       TEXT    NOT NULL,
                referente_interno   TEXT    DEFAULT '',
                referente_esterno   TEXT    DEFAULT '',
                data_inizio         TEXT    DEFAULT '',
                data_fine_prevista  TEXT    DEFAULT '',
                stato               TEXT    DEFAULT 'In corso',
                note                TEXT    DEFAULT '',
                created_at          TEXT    DEFAULT (datetime('now')),
                updated_at          TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS allocazioni (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                risorsa_id              INTEGER NOT NULL,
                progetto_id             INTEGER NOT NULL,
                data_inizio             TEXT    NOT NULL,
                data_fine               TEXT    NOT NULL,
                percentuale_allocazione REAL    NOT NULL DEFAULT 100.0,
                stato                   TEXT    DEFAULT 'Confermata',
                note                    TEXT    DEFAULT '',
                created_at              TEXT    DEFAULT (datetime('now')),
                updated_at              TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (risorsa_id)  REFERENCES risorse(id)  ON DELETE CASCADE,
                FOREIGN KEY (progetto_id) REFERENCES progetti(id) ON DELETE CASCADE
            );
            """
        )


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _rows_to_df(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])


# ---------------------------------------------------------------------------
# Risorse
# ---------------------------------------------------------------------------

def get_risorse(only_active: bool = False) -> pd.DataFrame:
    with _conn() as conn:
        q = "SELECT * FROM risorse"
        if only_active:
            q += " WHERE attivo = 1"
        q += " ORDER BY cognome, nome"
        rows = conn.execute(q).fetchall()
    df = _rows_to_df(rows)
    if not df.empty:
        df["competenze"] = df["competenze"].apply(
            lambda x: json.loads(x) if isinstance(x, str) else (x or [])
        )
    return df


def get_risorsa(risorsa_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM risorse WHERE id = ?", (risorsa_id,)
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["competenze"] = json.loads(d["competenze"]) if isinstance(d["competenze"], str) else []
    return d


def upsert_risorsa(data: dict) -> int:
    competenze = json.dumps(data.get("competenze", []))
    with _conn() as conn:
        if data.get("id"):
            conn.execute(
                """UPDATE risorse SET
                    nome=?, cognome=?, seniority=?, line_manager=?,
                    competenze=?, costo_giornaliero=?, costo_marginato=?,
                    attivo=?, updated_at=datetime('now')
                   WHERE id=?""",
                (
                    data["nome"], data["cognome"], data["seniority"],
                    data.get("line_manager", ""), competenze,
                    data.get("costo_giornaliero", 0), data.get("costo_marginato", 0),
                    int(data.get("attivo", 1)), data["id"],
                ),
            )
            return data["id"]
        cur = conn.execute(
            """INSERT INTO risorse
               (nome, cognome, seniority, line_manager, competenze,
                costo_giornaliero, costo_marginato, attivo)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                data["nome"], data["cognome"], data["seniority"],
                data.get("line_manager", ""), competenze,
                data.get("costo_giornaliero", 0), data.get("costo_marginato", 0),
                int(data.get("attivo", 1)),
            ),
        )
        return cur.lastrowid


def delete_risorsa(risorsa_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM risorse WHERE id = ?", (risorsa_id,))


# ---------------------------------------------------------------------------
# Progetti
# ---------------------------------------------------------------------------

def get_progetti() -> pd.DataFrame:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM progetti ORDER BY data_inizio DESC, nome_progetto"
        ).fetchall()
    return _rows_to_df(rows)


def get_progetto(progetto_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM progetti WHERE id = ?", (progetto_id,)
        ).fetchone()
    return dict(row) if row else None


def upsert_progetto(data: dict) -> int:
    with _conn() as conn:
        if data.get("id"):
            conn.execute(
                """UPDATE progetti SET
                    codice_esterno=?, codice_interno=?, nome_progetto=?,
                    referente_interno=?, referente_esterno=?,
                    data_inizio=?, data_fine_prevista=?, stato=?, note=?,
                    updated_at=datetime('now')
                   WHERE id=?""",
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
        cur = conn.execute(
            """INSERT INTO progetti
               (codice_esterno, codice_interno, nome_progetto,
                referente_interno, referente_esterno,
                data_inizio, data_fine_prevista, stato, note)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                data.get("codice_esterno", ""), data.get("codice_interno", ""),
                data["nome_progetto"],
                data.get("referente_interno", ""), data.get("referente_esterno", ""),
                data.get("data_inizio", ""), data.get("data_fine_prevista", ""),
                data.get("stato", "In corso"), data.get("note", ""),
            ),
        )
        return cur.lastrowid


def delete_progetto(progetto_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM progetti WHERE id = ?", (progetto_id,))


# ---------------------------------------------------------------------------
# Allocazioni
# ---------------------------------------------------------------------------

def get_allocazioni() -> pd.DataFrame:
    with _conn() as conn:
        rows = conn.execute(
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
        ).fetchall()
    return _rows_to_df(rows)


def get_allocazioni_risorsa(risorsa_id: int) -> pd.DataFrame:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT a.*, p.nome_progetto, p.stato AS progetto_stato
            FROM allocazioni a
            JOIN progetti p ON p.id = a.progetto_id
            WHERE a.risorsa_id = ?
            ORDER BY a.data_inizio
            """,
            (risorsa_id,),
        ).fetchall()
    return _rows_to_df(rows)


def upsert_allocazione(data: dict) -> int:
    with _conn() as conn:
        if data.get("id"):
            conn.execute(
                """UPDATE allocazioni SET
                    risorsa_id=?, progetto_id=?,
                    data_inizio=?, data_fine=?,
                    percentuale_allocazione=?, stato=?, note=?,
                    updated_at=datetime('now')
                   WHERE id=?""",
                (
                    data["risorsa_id"], data["progetto_id"],
                    data["data_inizio"], data["data_fine"],
                    data["percentuale_allocazione"],
                    data.get("stato", "Confermata"), data.get("note", ""),
                    data["id"],
                ),
            )
            return data["id"]
        cur = conn.execute(
            """INSERT INTO allocazioni
               (risorsa_id, progetto_id, data_inizio, data_fine,
                percentuale_allocazione, stato, note)
               VALUES (?,?,?,?,?,?,?)""",
            (
                data["risorsa_id"], data["progetto_id"],
                data["data_inizio"], data["data_fine"],
                data["percentuale_allocazione"],
                data.get("stato", "Confermata"), data.get("note", ""),
            ),
        )
        return cur.lastrowid


def delete_allocazione(allocazione_id: int) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM allocazioni WHERE id = ?", (allocazione_id,))


# ---------------------------------------------------------------------------
# Bulk import helpers
# ---------------------------------------------------------------------------

def bulk_insert_risorse(df: pd.DataFrame) -> tuple[int, list[str]]:
    """Returns (inserted_count, error_list)."""
    inserted, errors = 0, []
    for i, row in df.iterrows():
        try:
            competenze = []
            if "competenze" in row and pd.notna(row["competenze"]):
                raw = str(row["competenze"])
                competenze = [s.strip() for s in raw.split(";") if s.strip()]
            upsert_risorsa(
                {
                    "nome": str(row.get("nome", "")).strip(),
                    "cognome": str(row.get("cognome", "")).strip(),
                    "seniority": str(row.get("seniority", "Mid")).strip(),
                    "line_manager": str(row.get("line_manager", "")).strip(),
                    "competenze": competenze,
                    "costo_giornaliero": float(row.get("costo_giornaliero", 0) or 0),
                    "costo_marginato": float(row.get("costo_marginato", 0) or 0),
                    "attivo": 1,
                }
            )
            inserted += 1
        except Exception as exc:
            errors.append(f"Riga {i + 2}: {exc}")
    return inserted, errors


def bulk_insert_progetti(df: pd.DataFrame) -> tuple[int, list[str]]:
    inserted, errors = 0, []
    for i, row in df.iterrows():
        try:
            upsert_progetto(
                {
                    "codice_esterno": str(row.get("codice_esterno", "")).strip(),
                    "codice_interno": str(row.get("codice_interno", "")).strip(),
                    "nome_progetto": str(row.get("nome_progetto", "")).strip(),
                    "referente_interno": str(row.get("referente_interno", "")).strip(),
                    "referente_esterno": str(row.get("referente_esterno", "")).strip(),
                    "data_inizio": str(row.get("data_inizio", "")).strip(),
                    "data_fine_prevista": str(row.get("data_fine_prevista", "")).strip(),
                    "stato": str(row.get("stato", "In corso")).strip(),
                    "note": str(row.get("note", "")).strip(),
                }
            )
            inserted += 1
        except Exception as exc:
            errors.append(f"Riga {i + 2}: {exc}")
    return inserted, errors
