"""
SQLite audit storage and usage ledger for InfraSight (Phase 3).
Provides persistent tables for incidents, audit events, and usage ledger entries.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path("data/infrasight.db")


def get_db_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Initializes tables if they do not exist."""
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                device_id TEXT,
                bay_id TEXT,
                user_text TEXT,
                image_paths TEXT,
                final_status TEXT,
                confidence TEXT,
                summary TEXT,
                raw_diagnosis TEXT
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                step_number INTEGER NOT NULL,
                event_type TEXT NOT NULL, -- 'observation', 'tool_call', 'tool_result', 'policy_check', 'diagnosis'
                details TEXT NOT NULL,
                FOREIGN KEY (incident_id) REFERENCES incidents (incident_id)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_ledger (
                call_id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT,
                timestamp TEXT NOT NULL,
                purpose TEXT NOT NULL,
                model_id TEXT NOT NULL,
                reasoning_effort TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                cached_tokens INTEGER,
                total_tokens INTEGER,
                estimated_cost_usd REAL,
                latency_s REAL,
                is_replay INTEGER DEFAULT 0,
                missing_usage_flag INTEGER DEFAULT 0
            );
        """)
    conn.close()


def record_incident(
    incident_id: str,
    user_text: str,
    device_id: Optional[str] = None,
    bay_id: Optional[str] = None,
    image_paths: Optional[List[str]] = None,
    final_status: Optional[str] = None,
    confidence: Optional[str] = None,
    summary: Optional[str] = None,
    raw_diagnosis: Optional[Dict[str, Any]] = None,
    db_path: Path = DB_PATH
) -> None:
    init_db(db_path)
    conn = get_db_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO incidents (
                incident_id, created_at, device_id, bay_id, user_text, image_paths, final_status, confidence, summary, raw_diagnosis
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            incident_id,
            now,
            device_id,
            bay_id,
            user_text,
            json.dumps(image_paths or []),
            final_status,
            confidence,
            summary,
            json.dumps(raw_diagnosis or {})
        ))
    conn.close()


def record_audit_event(
    incident_id: str,
    step_number: int,
    event_type: str,
    details: Dict[str, Any],
    db_path: Path = DB_PATH
) -> None:
    init_db(db_path)
    conn = get_db_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT INTO audit_events (
                incident_id, timestamp, step_number, event_type, details
            ) VALUES (?, ?, ?, ?, ?);
        """, (
            incident_id,
            now,
            step_number,
            event_type,
            json.dumps(details)
        ))
    conn.close()


def record_usage(
    purpose: str,
    model_id: str,
    usage: Dict[str, Any],
    incident_id: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    latency_s: float = 0.0,
    is_replay: bool = False,
    db_path: Path = DB_PATH
) -> None:
    init_db(db_path)
    conn = get_db_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()

    p_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    c_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
    t_tokens = usage.get("total_tokens") or (p_tokens + c_tokens)
    p_details = usage.get("prompt_tokens_details") or {}
    cached = p_details.get("cached_tokens") or 0

    missing_flag = 1 if (p_tokens == 0 and c_tokens == 0 and not is_replay) else 0

    # Pricing per million tokens (Muse Spark rate: $0.30/M input, $0.90/M output approx)
    cost = (p_tokens * 0.30 / 1_000_000) + (c_tokens * 0.90 / 1_000_000)

    with conn:
        conn.execute("""
            INSERT INTO usage_ledger (
                incident_id, timestamp, purpose, model_id, reasoning_effort,
                prompt_tokens, completion_tokens, cached_tokens, total_tokens,
                estimated_cost_usd, latency_s, is_replay, missing_usage_flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            incident_id,
            now,
            purpose,
            model_id,
            reasoning_effort,
            p_tokens,
            c_tokens,
            cached,
            t_tokens,
            cost,
            latency_s,
            1 if is_replay else 0,
            missing_flag
        ))
    conn.close()


def get_incident_audit_trail(incident_id: str, db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.execute("""
        SELECT event_id, incident_id, timestamp, step_number, event_type, details
        FROM audit_events
        WHERE incident_id = ?
        ORDER BY step_number ASC, event_id ASC;
    """, (incident_id,))
    rows = cursor.fetchall()
    events = []
    for r in rows:
        events.append({
            "event_id": r["event_id"],
            "incident_id": r["incident_id"],
            "timestamp": r["timestamp"],
            "step_number": r["step_number"],
            "event_type": r["event_type"],
            "details": json.loads(r["details"])
        })
    conn.close()
    return events
