# feedback_store.py
"""
SQLite-backed store for query logging, user feedback, and performance telemetry.

Tables:
  query_log  — every SQL generation attempt (provider, latency, cache hit)
  feedback   — thumbs-up / thumbs-down ratings keyed to a query+sql pair

Used by:
  app.py                  — log_query(), record_feedback()
  pages/Admin_Dashboard.py — get_stats(), get_recent_feedback()
"""

import sqlite3
import os
import time
from typing import Optional, List, Dict, Any

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feedback.db")

# ── Internal helpers ──────────────────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    """Open connection and ensure tables exist."""
    c = sqlite3.connect(_DB_PATH, check_same_thread=False)
    c.execute("PRAGMA journal_mode=WAL")  # better concurrent write performance
    c.executescript("""
        CREATE TABLE IF NOT EXISTS query_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         REAL    NOT NULL,
            nl_query   TEXT    NOT NULL,
            sql_text   TEXT    NOT NULL,
            provider   TEXT,
            latency_ms REAL,
            row_count  INTEGER,
            cache_hit  INTEGER DEFAULT 0   -- 1 = returned from cache
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         REAL    NOT NULL,
            nl_query   TEXT    NOT NULL,
            sql_text   TEXT    NOT NULL,
            rating     INTEGER NOT NULL,   -- 1 = thumbs-up, -1 = thumbs-down
            provider   TEXT,
            latency_ms REAL,
            row_count  INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_qlog_ts ON query_log(ts);
        CREATE INDEX IF NOT EXISTS idx_fb_ts   ON feedback(ts);
    """)
    c.commit()
    return c


# ── Public write API ──────────────────────────────────────────────────────────

def log_query(
    nl_query: str,
    sql_text: str,
    provider: str = "",
    latency_ms: Optional[float] = None,
    row_count: Optional[int] = None,
    cache_hit: bool = False,
) -> None:
    """Record every successful SQL generation."""
    try:
        c = _conn()
        c.execute(
            "INSERT INTO query_log (ts, nl_query, sql_text, provider, latency_ms, row_count, cache_hit) "
            "VALUES (?,?,?,?,?,?,?)",
            (time.time(), nl_query[:2000], sql_text[:4000],
             provider or "", latency_ms, row_count, int(cache_hit)),
        )
        c.commit()
        c.close()
    except Exception:
        pass  # logging must never crash the app


def record_feedback(
    nl_query: str,
    sql_text: str,
    rating: int,                        # 1 = 👍, -1 = 👎
    provider: str = "",
    latency_ms: Optional[float] = None,
    row_count: Optional[int] = None,
) -> None:
    """Store user feedback for a query result."""
    try:
        c = _conn()
        c.execute(
            "INSERT INTO feedback (ts, nl_query, sql_text, rating, provider, latency_ms, row_count) "
            "VALUES (?,?,?,?,?,?,?)",
            (time.time(), nl_query[:2000], sql_text[:4000],
             rating, provider or "", latency_ms, row_count),
        )
        c.commit()
        c.close()
    except Exception:
        pass


# ── Public read API ───────────────────────────────────────────────────────────

def get_stats() -> Dict[str, Any]:
    """
    Aggregate telemetry for the Admin Dashboard.
    Returns a dict with KPIs, time-series, and breakdown data.
    """
    try:
        c = _conn()

        total_queries = c.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
        total_feedback = c.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        thumbs_up = c.execute("SELECT COUNT(*) FROM feedback WHERE rating=1").fetchone()[0]
        thumbs_down = c.execute("SELECT COUNT(*) FROM feedback WHERE rating=-1").fetchone()[0]

        # Average generation latency
        row = c.execute("SELECT AVG(latency_ms) FROM query_log WHERE latency_ms IS NOT NULL").fetchone()
        avg_latency_ms = round(row[0], 1) if row and row[0] else 0.0

        # Cache hit rate
        row = c.execute("SELECT AVG(cache_hit) FROM query_log").fetchone()
        cache_hit_rate_pct = round((row[0] or 0.0) * 100, 1)

        # Accuracy rate (positive feedback / total feedback)
        accuracy_pct = round((thumbs_up / total_feedback * 100), 1) if total_feedback else 0.0

        # Provider breakdown
        rows = c.execute(
            "SELECT provider, COUNT(*) cnt FROM query_log "
            "WHERE provider IS NOT NULL AND provider != '' "
            "GROUP BY provider ORDER BY cnt DESC"
        ).fetchall()
        provider_breakdown = {r[0]: r[1] for r in rows}

        # Queries per day (last 14 days)
        rows = c.execute("""
            SELECT date(ts, 'unixepoch', 'localtime') AS day, COUNT(*) cnt
            FROM query_log
            WHERE ts >= strftime('%s','now','-14 days')
            GROUP BY day ORDER BY day
        """).fetchall()
        queries_per_day = [{"day": r[0], "count": r[1]} for r in rows]

        # Latency trend (last 50 queries)
        rows = c.execute(
            "SELECT ts, latency_ms FROM query_log "
            "WHERE latency_ms IS NOT NULL ORDER BY ts DESC LIMIT 50"
        ).fetchall()
        latency_history = [{"ts": r[0], "latency_ms": r[1]} for r in reversed(rows)]

        # Top 10 most asked questions
        rows = c.execute(
            "SELECT nl_query, COUNT(*) cnt FROM query_log "
            "GROUP BY nl_query ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        top_queries = [{"query": r[0], "count": r[1]} for r in rows]

        # Recent queries (last 20)
        rows = c.execute(
            "SELECT ts, nl_query, provider, latency_ms, row_count, cache_hit "
            "FROM query_log ORDER BY ts DESC LIMIT 20"
        ).fetchall()
        recent_queries = [
            {"ts": r[0], "nl_query": r[1], "provider": r[2],
             "latency_ms": r[3], "row_count": r[4], "cache_hit": bool(r[5])}
            for r in rows
        ]

        c.close()

        return {
            "total_queries": total_queries,
            "total_feedback": total_feedback,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "avg_latency_ms": avg_latency_ms,
            "cache_hit_rate_pct": cache_hit_rate_pct,
            "accuracy_pct": accuracy_pct,
            "provider_breakdown": provider_breakdown,
            "queries_per_day": queries_per_day,
            "latency_history": latency_history,
            "top_queries": top_queries,
            "recent_queries": recent_queries,
        }
    except Exception as e:
        return {"error": str(e)}


def get_recent_feedback(n: int = 30) -> List[Dict]:
    """Return the n most recent feedback entries."""
    try:
        c = _conn()
        rows = c.execute(
            "SELECT ts, nl_query, sql_text, rating, provider, row_count "
            "FROM feedback ORDER BY ts DESC LIMIT ?",
            (n,),
        ).fetchall()
        c.close()
        return [
            {"ts": r[0], "nl_query": r[1], "sql": r[2],
             "rating": r[3], "provider": r[4], "row_count": r[5]}
            for r in rows
        ]
    except Exception:
        return []


def clear_all(confirm: bool = False) -> None:
    """Delete all records — requires confirm=True to prevent accidental calls."""
    if not confirm:
        return
    try:
        c = _conn()
        c.execute("DELETE FROM query_log")
        c.execute("DELETE FROM feedback")
        c.commit()
        c.close()
    except Exception:
        pass
