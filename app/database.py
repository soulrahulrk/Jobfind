from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DB_PATH, SAVED_SEARCHES


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS job_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL,
            url TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            config_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dedupe_key TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            source_job_id TEXT,
            title TEXT NOT NULL,
            company TEXT,
            location TEXT,
            remote INTEGER NOT NULL DEFAULT 0,
            salary_min INTEGER,
            salary_max INTEGER,
            salary_text TEXT,
            experience_min REAL,
            experience_max REAL,
            apply_url TEXT,
            posted_at TEXT,
            raw_text TEXT,
            raw_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS job_matches (
            job_id INTEGER PRIMARY KEY,
            match_score INTEGER NOT NULL,
            match_reasons TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS application_statuses (
            job_id INTEGER PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'new',
            notes TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()
    seed_sources(conn)


def seed_sources(conn: sqlite3.Connection) -> None:
    defaults = [
        {"name": "Remotive", "kind": "api", "url": "https://remotive.com/api/remote-jobs"},
        {"name": "Himalayas", "kind": "api", "url": "https://himalayas.app/jobs/api/search"},
        {"name": "Jobicy", "kind": "api", "url": "https://jobicy.com/api/v2/remote-jobs"},
        {"name": "Adzuna", "kind": "api", "url": "https://api.adzuna.com/v1/api/jobs/in/search/1"},
        {"name": "Gmail Job Alerts", "kind": "gmail", "url": None},
    ]
    defaults.extend({"name": item["name"], "kind": "saved_search", "url": item["url"]} for item in SAVED_SEARCHES)
    for item in defaults:
        upsert_source(conn, item)


def upsert_source(conn: sqlite3.Connection, source: dict[str, Any]) -> None:
    timestamp = now_iso()
    conn.execute(
        """
        INSERT INTO job_sources (name, kind, url, enabled, config_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            kind=excluded.kind,
            url=excluded.url,
            enabled=excluded.enabled,
            config_json=excluded.config_json,
            updated_at=excluded.updated_at
        """,
        (
            source["name"],
            source["kind"],
            source.get("url"),
            1 if source.get("enabled", True) else 0,
            json.dumps(source.get("config", {})),
            timestamp,
            timestamp,
        ),
    )
    conn.commit()


def list_sources(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM job_sources ORDER BY kind, name").fetchall()
    return [_row_to_dict(row) | {"config": json.loads(row["config_json"] or "{}")} for row in rows]


def upsert_profile(conn: sqlite3.Connection, profile: dict[str, Any]) -> None:
    timestamp = now_iso()
    for key, value in profile.items():
        conn.execute(
            """
            INSERT INTO profile (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key, json.dumps(value), timestamp),
        )
    conn.commit()


def get_profile(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("SELECT key, value FROM profile").fetchall()
    return {row["key"]: json.loads(row["value"]) for row in rows}


def upsert_job(conn: sqlite3.Connection, job: dict[str, Any], score: int, reasons: list[str]) -> int:
    timestamp = now_iso()
    dedupe_key = job.get("dedupe_key") or make_dedupe_key(job)
    salary_min, salary_max = job.get("salary_min"), job.get("salary_max")
    raw_json = json.dumps(job.get("raw_json", {}), ensure_ascii=True)
    conn.execute(
        """
        INSERT INTO jobs (
            dedupe_key, source, source_job_id, title, company, location, remote,
            salary_min, salary_max, salary_text, experience_min, experience_max,
            apply_url, posted_at, raw_text, raw_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(dedupe_key) DO UPDATE SET
            source=excluded.source,
            source_job_id=excluded.source_job_id,
            title=excluded.title,
            company=excluded.company,
            location=excluded.location,
            remote=excluded.remote,
            salary_min=excluded.salary_min,
            salary_max=excluded.salary_max,
            salary_text=excluded.salary_text,
            experience_min=excluded.experience_min,
            experience_max=excluded.experience_max,
            apply_url=excluded.apply_url,
            posted_at=excluded.posted_at,
            raw_text=excluded.raw_text,
            raw_json=excluded.raw_json,
            updated_at=excluded.updated_at
        """,
        (
            dedupe_key,
            job["source"],
            job.get("source_job_id"),
            job["title"],
            job.get("company"),
            job.get("location"),
            1 if job.get("remote") else 0,
            salary_min,
            salary_max,
            job.get("salary_text"),
            job.get("experience_min"),
            job.get("experience_max"),
            job.get("apply_url"),
            job.get("posted_at"),
            job.get("raw_text"),
            raw_json,
            timestamp,
            timestamp,
        ),
    )
    job_id = int(conn.execute("SELECT id FROM jobs WHERE dedupe_key = ?", (dedupe_key,)).fetchone()["id"])
    conn.execute(
        """
        INSERT INTO job_matches (job_id, match_score, match_reasons, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            match_score=excluded.match_score,
            match_reasons=excluded.match_reasons,
            updated_at=excluded.updated_at
        """,
        (job_id, score, json.dumps(reasons), timestamp),
    )
    conn.execute(
        """
        INSERT INTO application_statuses (job_id, status, notes, updated_at)
        VALUES (?, 'new', '', ?)
        ON CONFLICT(job_id) DO NOTHING
        """,
        (job_id, timestamp),
    )
    conn.commit()
    return job_id


def list_jobs(conn: sqlite3.Connection, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    filters = filters or {}
    clauses = ["1=1"]
    params: list[Any] = []

    if filters.get("q"):
        clauses.append("(LOWER(j.title) LIKE ? OR LOWER(j.company) LIKE ? OR LOWER(j.raw_text) LIKE ?)")
        q = f"%{str(filters['q']).lower()}%"
        params.extend([q, q, q])
    if filters.get("source"):
        clauses.append("j.source = ?")
        params.append(filters["source"])
    if filters.get("status"):
        clauses.append("s.status = ?")
        params.append(filters["status"])
    if filters.get("remote") in (True, "true", "1", 1):
        clauses.append("j.remote = 1")
    if filters.get("min_score") is not None:
        clauses.append("m.match_score >= ?")
        params.append(int(filters["min_score"]))
    if filters.get("salary_floor") in (True, "true", "1", 1):
        clauses.append("(j.salary_min IS NULL OR j.salary_min >= 10000)")

    query = f"""
        SELECT
            j.*,
            m.match_score,
            m.match_reasons,
            s.status,
            s.notes
        FROM jobs j
        JOIN job_matches m ON m.job_id = j.id
        JOIN application_statuses s ON s.job_id = j.id
        WHERE {' AND '.join(clauses)}
        ORDER BY m.match_score DESC, COALESCE(j.posted_at, j.created_at) DESC
    """
    rows = conn.execute(query, params).fetchall()
    return [_job_row_to_dict(row) for row in rows]


def update_status(conn: sqlite3.Connection, job_id: int, status: str, notes: str | None = None) -> dict[str, Any]:
    allowed = {"new", "saved", "applied", "rejected", "interview", "offer"}
    if status not in allowed:
        raise ValueError(f"Unsupported status: {status}")
    timestamp = now_iso()
    existing = conn.execute("SELECT notes FROM application_statuses WHERE job_id = ?", (job_id,)).fetchone()
    if not existing:
        raise KeyError(f"Job {job_id} not found")
    conn.execute(
        """
        UPDATE application_statuses
        SET status = ?, notes = ?, updated_at = ?
        WHERE job_id = ?
        """,
        (status, notes if notes is not None else existing["notes"], timestamp, job_id),
    )
    conn.commit()
    row = conn.execute(
        """
        SELECT j.*, m.match_score, m.match_reasons, s.status, s.notes
        FROM jobs j
        JOIN job_matches m ON m.job_id = j.id
        JOIN application_statuses s ON s.job_id = j.id
        WHERE j.id = ?
        """,
        (job_id,),
    ).fetchone()
    return _job_row_to_dict(row)


def make_dedupe_key(job: dict[str, Any]) -> str:
    material = "|".join(
        str(job.get(key) or "").strip().lower()
        for key in ("source", "source_job_id", "apply_url", "title", "company")
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _job_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = _row_to_dict(row)
    data["remote"] = bool(data["remote"])
    data["match_reasons"] = json.loads(data["match_reasons"] or "[]")
    data["raw_json"] = json.loads(data["raw_json"] or "{}")
    return data


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}
