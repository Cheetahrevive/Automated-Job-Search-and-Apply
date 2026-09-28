"""SQLite tracking store. Jobs are deduped by (source, external_id).

Status lifecycle: new -> reviewed | saved | skipped | applied
"""
from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import asdict

from jobsearch.sources.base import Job

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    source      TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title       TEXT NOT NULL,
    company     TEXT NOT NULL,
    location    TEXT DEFAULT '',
    remote      INTEGER DEFAULT 0,
    url         TEXT DEFAULT '',
    description TEXT DEFAULT '',
    salary_raw  TEXT DEFAULT '',
    posted_at   TEXT DEFAULT '',
    tags        TEXT DEFAULT '',
    fit_score   REAL DEFAULT 0,
    status      TEXT DEFAULT 'new',
    notes       TEXT DEFAULT '',
    seen_at     REAL DEFAULT 0,
    PRIMARY KEY (source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(fit_score);
"""

VALID_STATUSES = {"new", "reviewed", "saved", "skipped", "applied"}


class Store:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # -- writes ---------------------------------------------------------
    def upsert_jobs(self, jobs: list[Job], notes_for: dict | None = None) -> tuple[int, int]:
        """Insert new jobs / refresh score+notes of existing ones.
        Returns (inserted, updated)."""
        notes_for = notes_for or {}
        inserted = updated = 0
        now = time.time()
        for job in jobs:
            notes = notes_for.get((job.source, job.external_id), "")
            cur = self.conn.execute(
                "SELECT 1 FROM jobs WHERE source=? AND external_id=?",
                (job.source, job.external_id),
            )
            exists = cur.fetchone() is not None
            self.conn.execute(
                """INSERT INTO jobs
                   (source, external_id, title, company, location, remote, url,
                    description, salary_raw, posted_at, tags, fit_score, notes, seen_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(source, external_id) DO UPDATE SET
                     title=excluded.title, company=excluded.company,
                     location=excluded.location, remote=excluded.remote,
                     url=excluded.url, description=excluded.description,
                     salary_raw=excluded.salary_raw, posted_at=excluded.posted_at,
                     tags=excluded.tags, fit_score=excluded.fit_score,
                     notes=excluded.notes, seen_at=excluded.seen_at""",
                (
                    job.source, job.external_id, job.title, job.company,
                    job.location, int(job.remote), job.url, job.description,
                    job.salary_raw, job.posted_at, ",".join(job.tags or []),
                    job.fit_score, notes, now,
                ),
            )
            if exists:
                updated += 1
            else:
                inserted += 1
        self.conn.commit()
        return inserted, updated

    def set_status(self, job_id: int, status: str) -> bool:
        if status not in VALID_STATUSES:
            raise ValueError(f"invalid status {status!r}; use one of {sorted(VALID_STATUSES)}")
        cur = self.conn.execute("UPDATE jobs SET status=? WHERE rowid=?", (status, job_id))
        self.conn.commit()
        return cur.rowcount > 0

    # -- reads ----------------------------------------------------------
    def get(self, job_id: int) -> dict | None:
        cur = self.conn.execute("SELECT rowid AS id, * FROM jobs WHERE rowid=?", (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def list(self, min_score: float = 0, status: str | None = None,
             limit: int = 50) -> list[dict]:
        sql = "SELECT rowid AS id, * FROM jobs WHERE fit_score >= ?"
        params: list = [min_score]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY fit_score DESC, seen_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self.conn.execute(sql, params)]

    def stats(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        by_status = {
            r["status"]: r["n"]
            for r in self.conn.execute(
                "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"
            )
        }
        avg = self.conn.execute(
            "SELECT AVG(fit_score) FROM jobs WHERE status='new'"
        ).fetchone()[0]
        by_source = {
            r["source"]: r["n"]
            for r in self.conn.execute(
                "SELECT source, COUNT(*) AS n FROM jobs GROUP BY source"
            )
        }
        return {
            "total": total,
            "by_status": by_status,
            "avg_score_new": round(avg or 0, 1),
            "by_source": by_source,
        }

    def close(self):
        self.conn.close()
