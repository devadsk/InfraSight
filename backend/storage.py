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


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target = db_path if db_path is not None else DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
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
                raw_diagnosis TEXT,
                mode TEXT DEFAULT 'live'
            );
        """)
        # Migration for existing incidents table if mode column does not exist
        try:
            conn.execute("ALTER TABLE incidents ADD COLUMN mode TEXT DEFAULT 'live';")
        except sqlite3.OperationalError:
            pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                step_number INTEGER NOT NULL,
                event_type TEXT NOT NULL,
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_actions (
                action_id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                canonical_args TEXT NOT NULL,
                args_hash TEXT NOT NULL,
                status TEXT NOT NULL, -- 'pending', 'approved', 'rejected', 'expired', 'executed', 'failed'
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                decided_by TEXT,
                decided_at TEXT,
                executed_at TEXT,
                result_ref TEXT,
                FOREIGN KEY (incident_id) REFERENCES incidents (incident_id)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sim_state (
                incident_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                state_data TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (incident_id, device_id)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sim_tickets (
                ticket_id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                summary TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                actions TEXT NOT NULL,
                status TEXT NOT NULL,
                is_simulated INTEGER DEFAULT 1,
                FOREIGN KEY (incident_id) REFERENCES incidents (incident_id)
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incident_state (
                incident_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                step_number INTEGER NOT NULL,
                resolved_device_id TEXT,
                resolved_bay_id TEXT,
                evidence_ids TEXT NOT NULL,
                messages TEXT NOT NULL,
                pending_action_id TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (incident_id) REFERENCES incidents (incident_id)
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
    mode: str = "live",
    db_path: Optional[Path] = None
) -> None:
    init_db(db_path)
    conn = get_db_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO incidents (
                incident_id, created_at, device_id, bay_id, user_text, image_paths, final_status, confidence, summary, raw_diagnosis, mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
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
            json.dumps(raw_diagnosis or {}),
            mode
        ))
    conn.close()


def record_audit_event(
    incident_id: str,
    step_number: int,
    event_type: str,
    details: Dict[str, Any],
    db_path: Optional[Path] = None
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
    db_path: Optional[Path] = None
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


def get_incident_audit_trail(incident_id: str, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
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


# ---------------------------------------------------------------------------
# Pending Actions Operations (B2 Server-side Record)
# ---------------------------------------------------------------------------

def record_pending_action(
    action_id: str,
    incident_id: str,
    tool: str,
    canonical_args: str,
    args_hash: str,
    expires_at: str,
    status: str = "pending",
    db_path: Optional[Path] = None,
) -> None:
    init_db(db_path)
    conn = get_db_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO pending_actions (
                action_id, incident_id, tool, canonical_args, args_hash,
                status, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            action_id, incident_id, tool, canonical_args, args_hash,
            status, now, expires_at
        ))
    conn.close()


def get_pending_action(action_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.execute("""
        SELECT action_id, incident_id, tool, canonical_args, args_hash,
               status, created_at, expires_at, decided_by, decided_at,
               executed_at, result_ref
        FROM pending_actions
        WHERE action_id = ?;
    """, (action_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def get_pending_actions_for_incident(incident_id: str, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.execute("""
        SELECT action_id, incident_id, tool, canonical_args, args_hash,
               status, created_at, expires_at, decided_by, decided_at,
               executed_at, result_ref
        FROM pending_actions
        WHERE incident_id = ?
        ORDER BY created_at ASC;
    """, (incident_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_action_status(
    action_id: str,
    status: str,
    decided_by: Optional[str] = None,
    decided_at: Optional[str] = None,
    executed_at: Optional[str] = None,
    result_ref: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    init_db(db_path)
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            UPDATE pending_actions
            SET status = ?,
                decided_by = COALESCE(?, decided_by),
                decided_at = COALESCE(?, decided_at),
                executed_at = COALESCE(?, executed_at),
                result_ref = COALESCE(?, result_ref)
            WHERE action_id = ?;
        """, (status, decided_by, decided_at, executed_at, result_ref, action_id))
    conn.close()


# ---------------------------------------------------------------------------
# Simulated State Operations (B3 Mutable Copy in SQLite)
# ---------------------------------------------------------------------------

def save_sim_state(
    incident_id: str,
    device_id: str,
    state_dict: Dict[str, Any],
    db_path: Optional[Path] = None,
) -> None:
    init_db(db_path)
    conn = get_db_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO sim_state (
                incident_id, device_id, state_data, updated_at
            ) VALUES (?, ?, ?, ?);
        """, (incident_id, device_id, json.dumps(state_dict), now))
    conn.close()


def get_sim_state(
    incident_id: str,
    device_id: str,
    db_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.execute("""
        SELECT state_data FROM sim_state
        WHERE incident_id = ? AND device_id = ?;
    """, (incident_id, device_id))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return json.loads(row["state_data"])


# ---------------------------------------------------------------------------
# Simulated Tickets (B3)
# ---------------------------------------------------------------------------

def save_sim_ticket(
    ticket_id: str,
    incident_id: str,
    summary: str,
    diagnosis: str,
    actions: str,
    status: str,
    is_simulated: int = 1,
    db_path: Optional[Path] = None,
) -> None:
    init_db(db_path)
    conn = get_db_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO sim_tickets (
                ticket_id, incident_id, created_at, summary, diagnosis, actions, status, is_simulated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (ticket_id, incident_id, now, summary, diagnosis, actions, status, is_simulated))
    conn.close()


def get_sim_tickets(incident_id: str, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.execute("""
        SELECT ticket_id, incident_id, created_at, summary, diagnosis, actions, status, is_simulated
        FROM sim_tickets
        WHERE incident_id = ?
        ORDER BY created_at ASC;
    """, (incident_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Resumable Incident State Operations (B4)
# ---------------------------------------------------------------------------

def save_incident_state(
    incident_id: str,
    status: str,
    step_number: int,
    resolved_device_id: Optional[str],
    resolved_bay_id: Optional[str],
    evidence_ids: List[str],
    messages: List[Dict[str, Any]],
    pending_action_id: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    init_db(db_path)
    conn = get_db_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO incident_state (
                incident_id, status, step_number, resolved_device_id, resolved_bay_id,
                evidence_ids, messages, pending_action_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            incident_id, status, step_number, resolved_device_id, resolved_bay_id,
            json.dumps(evidence_ids), json.dumps(messages), pending_action_id, now
        ))
    conn.close()


def get_incident_state(incident_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.execute("""
        SELECT incident_id, status, step_number, resolved_device_id, resolved_bay_id,
               evidence_ids, messages, pending_action_id, updated_at
        FROM incident_state
        WHERE incident_id = ?;
    """, (incident_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "incident_id": row["incident_id"],
        "status": row["status"],
        "step_number": row["step_number"],
        "resolved_device_id": row["resolved_device_id"],
        "resolved_bay_id": row["resolved_bay_id"],
        "evidence_ids": json.loads(row["evidence_ids"]),
        "messages": json.loads(row["messages"]),
        "pending_action_id": row["pending_action_id"],
        "updated_at": row["updated_at"],
    }


def get_incident(incident_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.execute("""
        SELECT incident_id, created_at, device_id, bay_id, user_text,
               image_paths, final_status, confidence, summary, raw_diagnosis, mode
        FROM incidents
        WHERE incident_id = ?;
    """, (incident_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "incident_id": row["incident_id"],
        "created_at": row["created_at"],
        "device_id": row["device_id"],
        "bay_id": row["bay_id"],
        "user_text": row["user_text"],
        "image_paths": json.loads(row["image_paths"] or "[]"),
        "final_status": row["final_status"],
        "confidence": row["confidence"],
        "summary": row["summary"],
        "raw_diagnosis": json.loads(row["raw_diagnosis"] or "{}"),
        "mode": row["mode"] or "live",
    }


def update_incident_status(
    incident_id: str,
    final_status: str,
    summary: Optional[str] = None,
    confidence: Optional[str] = None,
    raw_diagnosis: Optional[Dict[str, Any]] = None,
    mode: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> None:
    init_db(db_path)
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            UPDATE incidents
            SET final_status = ?,
                summary = COALESCE(?, summary),
                confidence = COALESCE(?, confidence),
                raw_diagnosis = COALESCE(?, raw_diagnosis),
                mode = COALESCE(?, mode)
            WHERE incident_id = ?;
        """, (
            final_status,
            summary,
            confidence,
            json.dumps(raw_diagnosis) if raw_diagnosis is not None else None,
            mode,
            incident_id,
        ))
    conn.close()


def get_usage_summary(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Returns cumulative usage statistics across all incidents."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.execute("""
        SELECT COUNT(*) as total_calls,
               COALESCE(SUM(total_tokens), 0) as total_tokens,
               COALESCE(SUM(estimated_cost_usd), 0.0) as total_cost_usd
        FROM usage_ledger;
    """)
    row = cursor.fetchone()
    total_calls = row["total_calls"]
    total_tokens = row["total_tokens"]
    total_cost_usd = row["total_cost_usd"]

    # By Purpose
    cursor = conn.execute("""
        SELECT purpose, model_id, COUNT(*) as call_count,
               SUM(total_tokens) as tokens, SUM(estimated_cost_usd) as cost_usd
        FROM usage_ledger
        GROUP BY purpose, model_id
        ORDER BY tokens DESC;
    """)
    by_purpose = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost_usd, 6),
        "by_purpose": by_purpose,
    }


def get_incident_usage(incident_id: str, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Returns per-call usage entries for a specific incident."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.execute("""
        SELECT call_id, timestamp, purpose, model_id, reasoning_effort,
               prompt_tokens, completion_tokens, cached_tokens, total_tokens,
               estimated_cost_usd, latency_s, is_replay
        FROM usage_ledger
        WHERE incident_id = ?
        ORDER BY call_id ASC;
    """, (incident_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    total_tokens = sum(r.get("total_tokens", 0) for r in rows)
    total_cost = sum(r.get("estimated_cost_usd", 0.0) for r in rows)

    return {
        "incident_id": incident_id,
        "call_count": len(rows),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6),
        "calls": rows,
    }

