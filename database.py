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
        connect_timeout=10,
        sslmode="require",
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
@st.cache_resource
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
                    competenze          TEXT    DEFAULT '{}',
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

            # indici unique necessari per ON CONFLICT nei bulk insert
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_risorse_nome_cognome
                ON risorse (nome, cognome);
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_progetti_unique
                ON progetti (nome_progetto, codice_interno, codice_esterno);
                """
            )

            # Nuove colonne aggiunte in modo idempotente
            for col_def in [
                "ALTER TABLE risorse ADD COLUMN IF NOT EXISTS email TEXT DEFAULT ''",
                "ALTER TABLE risorse ADD COLUMN IF NOT EXISTS data_assunzione TEXT DEFAULT ''",
                "ALTER TABLE progetti ADD COLUMN IF NOT EXISTS tipo_progetto TEXT DEFAULT ''",
                "ALTER TABLE progetti ADD COLUMN IF NOT EXISTS cliente TEXT DEFAULT ''",
                "ALTER TABLE progetti ADD COLUMN IF NOT EXISTS margine REAL DEFAULT 0.0",
                "ALTER TABLE progetti ADD COLUMN IF NOT EXISTS ricavo_fisso REAL DEFAULT 0.0"
            ]:
                cur.execute(col_def)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _rows_to_df(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])


def _parse_competenze(raw) -> dict:
    """Normalise competenze from DB: handles both old list and new dict format."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {s: 0 for s in raw}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {s: 0 for s in parsed}
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


# ---------------------------------------------------------------------------
# Risorse
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
        df["competenze"] = df["competenze"].apply(_parse_competenze)
        if "email" not in df.columns:
            df["email"] = ""
        if "data_assunzione" not in df.columns:
            df["data_assunzione"] = ""
    return df


def get_risorsa(risorsa_id: int) -> dict | None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM risorse WHERE id = %s", (risorsa_id,))
            row = cur.fetchone()
    if row is None:
        return None
    d = dict(row)
    d["competenze"] = _parse_competenze(d.get("competenze"))
    return d


def upsert_risorsa(data: dict) -> int:
    competenze = json.dumps(data.get("competenze", {}))
    with _conn() as conn:
        with conn.cursor() as cur:
            if data.get("id"):
                cur.execute(
                    """UPDATE risorse SET
                        nome=%s, cognome=%s, seniority=%s, line_manager=%s,
                        competenze=%s, costo_giornaliero=%s, costo_marginato=%s,
                        attivo=%s, email=%s, data_assunzione=%s,
                        updated_at=NOW()
                       WHERE id=%s""",
                    (
                        data["nome"], data["cognome"], data["seniority"],
                        data.get("line_manager", ""), competenze,
                        data.get("costo_giornaliero", 0), data.get("costo_marginato", 0),
                        int(data.get("attivo", 1)),
                        data.get("email", ""), data.get("data_assunzione", ""),
                        data["id"],
                    ),
                )
                return data["id"]
            cur.execute(
                """INSERT INTO risorse
                   (nome, cognome, seniority, line_manager, competenze,
                    costo_giornaliero, costo_marginato, attivo, email, data_assunzione)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    data["nome"], data["cognome"], data["seniority"],
                    data.get("line_manager", ""), competenze,
                    data.get("costo_giornaliero", 0), data.get("costo_marginato", 0),
                    int(data.get("attivo", 1)),
                    data.get("email", ""), data.get("data_assunzione", ""),
                ),
            )
            return cur.fetchone()["id"]


def upsert_risorsa_competenze(risorsa_id: int, competenze: dict) -> None:
    """Aggiorna solo le competenze di una risorsa (usato dalla modalità utente)."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE risorse SET competenze=%s, updated_at=NOW() WHERE id=%s",
                (json.dumps(competenze), risorsa_id),
            )


def delete_risorsa(risorsa_id: int) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM risorse WHERE id = %s", (risorsa_id,))


# ---------------------------------------------------------------------------
# Progetti
# ---------------------------------------------------------------------------

def get_progetti() -> pd.DataFrame:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM progetti ORDER BY data_inizio DESC, nome_progetto"
            )
            rows = cur.fetchall()
    df = _rows_to_df(rows)
    if not df.empty and "tipo_progetto" not in df.columns:
        df["tipo_progetto"] = ""
    return df


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
                        tipo_progetto=%s,
                        updated_at=NOW()
                       WHERE id=%s""",
                    (
                        data.get("codice_esterno", ""), data.get("codice_interno", ""),
                        data["nome_progetto"],
                        data.get("referente_interno", ""), data.get("referente_esterno", ""),
                        data.get("data_inizio", ""), data.get("data_fine_prevista", ""),
                        data.get("stato", "In corso"), data.get("note", ""),
                        data.get("tipo_progetto", ""),
                        data["id"],
                    ),
                )
                return data["id"]
            cur.execute(
                """INSERT INTO progetti
                   (codice_esterno, codice_interno, nome_progetto,
                    referente_interno, referente_esterno,
                    data_inizio, data_fine_prevista, stato, note, tipo_progetto)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id""",
                (
                    data.get("codice_esterno", ""), data.get("codice_interno", ""),
                    data["nome_progetto"],
                    data.get("referente_interno", ""), data.get("referente_esterno", ""),
                    data.get("data_inizio", ""), data.get("data_fine_prevista", ""),
                    data.get("stato", "In corso"), data.get("note", ""),
                    data.get("tipo_progetto", ""),
                ),
            )
            return cur.fetchone()["id"]


def delete_progetto(progetto_id: int) -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM progetti WHERE id = %s", (progetto_id,))


# ---------------------------------------------------------------------------
# Allocazioni
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
# Bulk import helpers
# ---------------------------------------------------------------------------

def bulk_insert_risorse(df: pd.DataFrame) -> tuple[int, list[str]]:
    """Upsert bulk: inserisce o sovrascrive se nome+cognome già esistono."""
    inserted, errors = 0, []

    rows_to_insert: list[tuple] = []
    for i, row in df.iterrows():
        nome = str(row.get("nome", "") or "").strip()
        cognome = str(row.get("cognome", "") or "").strip()
        if not nome or nome == "nan":
            errors.append(f"Riga {i + 2}: campo 'nome' obbligatorio mancante")
            continue
        if not cognome or cognome == "nan":
            errors.append(f"Riga {i + 2}: campo 'cognome' obbligatorio mancante")
            continue
        try:
            costo_g = float(row.get("costo_giornaliero", 0) or 0)
            costo_m = float(row.get("costo_marginato", 0) or 0)
        except (ValueError, TypeError):
            errors.append(f"Riga {i + 2}: valori di costo non numerici")
            continue
        competenze: dict = {}
        if "competenze" in row and pd.notna(row["competenze"]):
            skills = [s.strip() for s in str(row["competenze"]).split(";") if s.strip()]
            competenze = {s: 0 for s in skills}
        email = str(row.get("email", "") or "").strip()
        data_assunzione = str(row.get("data_assunzione", "") or "").strip()
        rows_to_insert.append((
            i + 2,
            nome, cognome,
            str(row.get("seniority", "Mid") or "Mid").strip(),
            str(row.get("line_manager", "") or "").strip(),
            json.dumps(competenze),
            costo_g, costo_m,
            email, data_assunzione,
        ))

    if not rows_to_insert:
        return 0, errors

    with _conn() as conn:
        with conn.cursor() as cur:
            for row_num, nome, cognome, seniority, line_manager, competenze, costo_g, costo_m, email, data_assunzione in rows_to_insert:
                try:
                    cur.execute("SAVEPOINT bulk_row")
                    cur.execute(
                        """INSERT INTO risorse
                           (nome, cognome, seniority, line_manager, competenze,
                            costo_giornaliero, costo_marginato, attivo, email, data_assunzione)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s,%s)
                           ON CONFLICT (nome, cognome) DO UPDATE SET
                               seniority         = EXCLUDED.seniority,
                               line_manager      = EXCLUDED.line_manager,
                               competenze        = EXCLUDED.competenze,
                               costo_giornaliero = EXCLUDED.costo_giornaliero,
                               costo_marginato   = EXCLUDED.costo_marginato,
                               attivo            = EXCLUDED.attivo,
                               email             = EXCLUDED.email,
                               data_assunzione   = EXCLUDED.data_assunzione,
                               updated_at        = NOW()""",
                        (nome, cognome, seniority, line_manager, competenze, costo_g, costo_m, email, data_assunzione),
                    )
                    cur.execute("RELEASE SAVEPOINT bulk_row")
                    inserted += 1
                except Exception as exc:
                    cur.execute("ROLLBACK TO SAVEPOINT bulk_row")
                    cur.execute("RELEASE SAVEPOINT bulk_row")
                    errors.append(f"Riga {row_num}: {exc}")

    return inserted, errors


def bulk_insert_progetti(df: pd.DataFrame) -> tuple[int, list[str]]:
    """Upsert bulk: inserisce o sovrascrive se nome_progetto+codice_interno+codice_esterno già esistono."""
    inserted, errors = 0, []

    rows_to_insert: list[tuple] = []
    for i, row in df.iterrows():
        nome_progetto = str(row.get("nome_progetto", "") or "").strip()
        if not nome_progetto or nome_progetto == "nan":
            errors.append(f"Riga {i + 2}: campo 'nome_progetto' obbligatorio mancante")
            continue
        rows_to_insert.append((
            i + 2,
            str(row.get("codice_esterno", "") or "").strip(),
            str(row.get("codice_interno", "") or "").strip(),
            nome_progetto,
            str(row.get("referente_interno", "") or "").strip(),
            str(row.get("referente_esterno", "") or "").strip(),
            str(row.get("data_inizio", "") or "").strip(),
            str(row.get("data_fine_prevista", "") or "").strip(),
            str(row.get("stato", "In corso") or "In corso").strip(),
            str(row.get("note", "") or "").strip(),
            str(row.get("tipo_progetto", "") or "").strip(),
        ))

    if not rows_to_insert:
        return 0, errors

    with _conn() as conn:
        with conn.cursor() as cur:
            for row_num, cod_est, cod_int, nome, ref_int, ref_est, d_inizio, d_fine, stato, note, tipo in rows_to_insert:
                try:
                    cur.execute("SAVEPOINT bulk_row")
                    cur.execute(
                        """INSERT INTO progetti
                           (codice_esterno, codice_interno, nome_progetto,
                            referente_interno, referente_esterno,
                            data_inizio, data_fine_prevista, stato, note, tipo_progetto)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (nome_progetto, codice_interno, codice_esterno) DO UPDATE SET
                               referente_interno  = EXCLUDED.referente_interno,
                               referente_esterno  = EXCLUDED.referente_esterno,
                               data_inizio        = EXCLUDED.data_inizio,
                               data_fine_prevista = EXCLUDED.data_fine_prevista,
                               stato              = EXCLUDED.stato,
                               note               = EXCLUDED.note,
                               tipo_progetto      = EXCLUDED.tipo_progetto,
                               updated_at         = NOW()""",
                        (cod_est, cod_int, nome, ref_int, ref_est, d_inizio, d_fine, stato, note, tipo),
                    )
                    cur.execute("RELEASE SAVEPOINT bulk_row")
                    inserted += 1
                except Exception as exc:
                    cur.execute("ROLLBACK TO SAVEPOINT bulk_row")
                    cur.execute("RELEASE SAVEPOINT bulk_row")
                    errors.append(f"Riga {row_num}: {exc}")

    return inserted, errors
