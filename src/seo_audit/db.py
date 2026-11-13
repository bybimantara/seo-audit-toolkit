"""Lightweight SQLite persistence for SEO Audit Toolkit using Python standard library."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

from seo_audit.models import SiteAuditReport


def get_default_db_path() -> Path:
    """Resolve the default SQLite database path."""
    env_path = os.getenv("SEO_AUDIT_DB_PATH")
    if env_path:
        path = Path(env_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    base_dir = Path.home() / ".seo_audit"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "history.db"


_INITIALIZED_DBS: set[str] = set()


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Create and return a configured SQLite connection with WAL mode and tables initialized."""
    target_path = Path(db_path) if db_path is not None else get_default_db_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    db_key = str(target_path.resolve())
    if db_key not in _INITIALIZED_DBS:
        init_db(conn)
        _INITIALIZED_DBS.add(db_key)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize SQLite database tables and indices if not already present."""
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                target_url TEXT NOT NULL,
                audited_at TEXT NOT NULL,
                health_score INTEGER NOT NULL,
                pages_count INTEGER NOT NULL,
                broken_count INTEGER NOT NULL,
                duration_seconds REAL NOT NULL,
                report_json TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reports_url ON reports(target_url);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reports_audited_at ON reports(audited_at DESC);"
        )


def save_report(
    report: SiteAuditReport, db_path: str | Path | None = None
) -> SiteAuditReport:
    """Save a SiteAuditReport instance to SQLite database."""
    conn = get_connection(db_path)
    try:
        report_json = report.to_json()
        with conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO reports (
                    report_id, target_url, audited_at, health_score,
                    pages_count, broken_count, duration_seconds, report_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    report.report_id,
                    report.target_url,
                    report.audited_at,
                    report.health_score,
                    len(report.pages),
                    len(report.broken_links),
                    report.duration_seconds,
                    report_json,
                ),
            )
        return report
    finally:
        conn.close()


def get_report(
    report_id: str, db_path: str | Path | None = None
) -> SiteAuditReport | None:
    """Retrieve a full SiteAuditReport by its report_id."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT report_json FROM reports WHERE report_id = ? LIMIT 1;",
            (report_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return SiteAuditReport.from_json(row["report_json"])
    finally:
        conn.close()


def list_reports(
    limit: int = 50, domain: str | None = None, db_path: str | Path | None = None
) -> list[dict[str, Any]]:
    """List recent audit report summaries."""
    conn = get_connection(db_path)
    try:
        if domain:
            query = """
                SELECT report_id, target_url, audited_at, health_score,
                       pages_count, broken_count, duration_seconds
                FROM reports
                WHERE target_url LIKE ?
                ORDER BY audited_at DESC
                LIMIT ?;
            """
            cursor = conn.execute(query, (f"%{domain}%", limit))
        else:
            query = """
                SELECT report_id, target_url, audited_at, health_score,
                       pages_count, broken_count, duration_seconds
                FROM reports
                ORDER BY audited_at DESC
                LIMIT ?;
            """
            cursor = conn.execute(query, (limit,))

        rows = cursor.fetchall()
        return [
            {
                "report_id": row["report_id"],
                "target_url": row["target_url"],
                "audited_at": row["audited_at"],
                "health_score": row["health_score"],
                "pages_count": row["pages_count"],
                "broken_count": row["broken_count"],
                "duration_seconds": row["duration_seconds"],
            }
            for row in rows
        ]
    finally:
        conn.close()


def delete_report(report_id: str, db_path: str | Path | None = None) -> bool:
    """Delete a report by its report_id. Returns True if deleted."""
    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute(
                "DELETE FROM reports WHERE report_id = ?;", (report_id,)
            )
            return cursor.rowcount > 0
    finally:
        conn.close()
