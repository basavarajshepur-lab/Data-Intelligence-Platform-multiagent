"""Persistent SQLite memory for the metadata agent.

Stores run history and a field glossary so the agent can maintain
cross-dataset consistency for PII classification and sensitivity levels.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "outputs" / "memory.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    return sqlite3.connect(str(DB_PATH))


def _init() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS regulation_cache (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                source_key   TEXT NOT NULL,
                framework    TEXT,
                item_id      TEXT NOT NULL,
                headline     TEXT,
                url          TEXT,
                published_dt TEXT,
                summary      TEXT,
                fetched_at   TEXT DEFAULT (datetime('now')),
                UNIQUE(source_key, item_id)
            );
            CREATE INDEX IF NOT EXISTS idx_rc_fw
                ON regulation_cache(framework, fetched_at DESC);
            CREATE TABLE IF NOT EXISTS processed_sources (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type   TEXT NOT NULL,
                source_id     TEXT NOT NULL,
                filename      TEXT,
                success       INTEGER DEFAULT 1,
                processed_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(source_type, source_id)
            );
            CREATE INDEX IF NOT EXISTS idx_ps_lookup
                ON processed_sources(source_type, source_id);
            CREATE TABLE IF NOT EXISTS runs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_name  TEXT    NOT NULL,
                data_domain   TEXT,
                classification TEXT,
                field_count   INTEGER,
                pii_count     INTEGER,
                quality_score REAL,
                quality_passed INTEGER,
                metadata_json TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS field_glossary (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                field_name        TEXT NOT NULL,
                display_name      TEXT,
                description       TEXT,
                data_type         TEXT,
                is_pii            INTEGER DEFAULT 0,
                pii_type          TEXT,
                sensitivity_level TEXT,
                usage_guidance    TEXT,
                source_dataset    TEXT,
                run_id            INTEGER,
                created_at        TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_fg_name  ON field_glossary(field_name);
            CREATE INDEX IF NOT EXISTS idx_run_name ON runs(dataset_name);
        """)


def store_run(metadata, quality) -> int:
    """Persist a completed metadata run and populate the field glossary."""
    _init()
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO runs
               (dataset_name, data_domain, classification, field_count, pii_count,
                quality_score, quality_passed, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                metadata.dataset_name,
                metadata.data_domain.value,
                metadata.classification.value,
                len(metadata.fields),
                sum(1 for f in metadata.fields if f.is_pii),
                quality.overall_score if quality else None,
                int(quality.passed) if quality else None,
                metadata.model_dump_json(),
            ),
        )
        run_id = cur.lastrowid
        con.executemany(
            """INSERT INTO field_glossary
               (field_name, display_name, description, data_type, is_pii, pii_type,
                sensitivity_level, usage_guidance, source_dataset, run_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    f.name,
                    f.display_name,
                    f.description,
                    f.data_type.value,
                    int(f.is_pii),
                    f.pii_type.value if f.pii_type else None,
                    f.sensitivity_level.value,
                    f.usage_guidance,
                    metadata.dataset_name,
                    run_id,
                )
                for f in metadata.fields
            ],
        )
    return run_id


def search_glossary(field_names: list[str]) -> list[dict]:
    """Return the most-recent prior definition for each matching field name."""
    if not field_names:
        return []
    _init()
    placeholders = ",".join("?" * len(field_names))
    with _conn() as con:
        rows = con.execute(
            f"""SELECT field_name, display_name, description, data_type,
                       is_pii, pii_type, sensitivity_level, usage_guidance, source_dataset
                FROM field_glossary
                WHERE field_name IN ({placeholders})
                GROUP BY field_name
                HAVING MAX(created_at)
                ORDER BY field_name""",
            field_names,
        ).fetchall()
    return [
        {
            "field_name": r[0],
            "display_name": r[1],
            "description": r[2],
            "data_type": r[3],
            "is_pii": bool(r[4]),
            "pii_type": r[5],
            "sensitivity_level": r[6],
            "usage_guidance": r[7],
            "source_dataset": r[8],
        }
        for r in rows
    ]


def get_run_history(limit: int = 20) -> list[dict]:
    """Return lightweight summaries of the most recent runs."""
    _init()
    with _conn() as con:
        rows = con.execute(
            """SELECT id, dataset_name, data_domain, classification, field_count,
                      pii_count, quality_score, quality_passed, created_at
               FROM runs ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [
        {
            "id": r[0],
            "dataset_name": r[1],
            "data_domain": r[2],
            "classification": r[3],
            "field_count": r[4],
            "pii_count": r[5],
            "quality_score": r[6],
            "quality_passed": bool(r[7]) if r[7] is not None else None,
            "created_at": r[8],
        }
        for r in rows
    ]


def glossary_size() -> int:
    """Return total number of field entries in the glossary."""
    _init()
    with _conn() as con:
        return con.execute("SELECT COUNT(*) FROM field_glossary").fetchone()[0]


def is_processed(source_type: str, source_id: str) -> bool:
    """Return True if this source file has already been processed by the watcher."""
    _init()
    with _conn() as con:
        row = con.execute(
            "SELECT id FROM processed_sources WHERE source_type=? AND source_id=?",
            (source_type, source_id),
        ).fetchone()
    return row is not None


def mark_processed(source_type: str, source_id: str, filename: str, success: bool) -> None:
    """Record that the watcher processed a file from an external source."""
    _init()
    with _conn() as con:
        con.execute(
            """INSERT OR REPLACE INTO processed_sources
               (source_type, source_id, filename, success)
               VALUES (?, ?, ?, ?)""",
            (source_type, source_id, filename, int(success)),
        )


# ── Regulation cache ───────────────────────────────────────────────────────

def cache_regulation_items(source_key: str, framework: str, items: list[dict]) -> None:
    """Upsert a batch of RSS items into the regulation cache."""
    _init()
    with _conn() as con:
        con.executemany(
            """INSERT OR REPLACE INTO regulation_cache
               (source_key, framework, item_id, headline, url, published_dt, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    source_key,
                    framework,
                    item["item_id"],
                    item.get("headline", ""),
                    item.get("url", ""),
                    item.get("published_dt", ""),
                    item.get("summary", ""),
                )
                for item in items
            ],
        )


def get_cached_regulations(
    source_key: str | None = None,
    frameworks: list[str] | None = None,
    max_age_hours: int = 24,
    limit: int = 20,
) -> list[dict]:
    """Return cached regulation items that are younger than max_age_hours."""
    _init()
    clauses = ["fetched_at >= datetime('now', ?)"]
    params: list = [f"-{max_age_hours} hours"]

    if source_key:
        clauses.append("source_key = ?")
        params.append(source_key)

    if frameworks:
        placeholders = ",".join("?" * len(frameworks))
        clauses.append(f"framework IN ({placeholders})")
        params.extend(frameworks)

    where = " AND ".join(clauses)
    params.append(limit)

    with _conn() as con:
        rows = con.execute(
            f"""SELECT source_key, framework, headline, url, published_dt, summary, fetched_at
                FROM regulation_cache
                WHERE {where}
                ORDER BY framework, fetched_at DESC
                LIMIT ?""",
            params,
        ).fetchall()

    return [
        {
            "source_key": r[0],
            "framework": r[1],
            "headline": r[2],
            "url": r[3],
            "published_dt": r[4],
            "summary": r[5],
            "fetched_at": r[6],
        }
        for r in rows
    ]
