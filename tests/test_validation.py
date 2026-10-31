"""
Referential integrity test suite for pytest.
Runs validate_all() to guarantee zero broken references across scenarios,
devices, telemetry, manuals, images, and diagnostics.
"""

import pytest
from scripts.validate_data import validate_all


def test_referential_integrity():
    passed = validate_all()
    assert passed is True, "Referential integrity validation failed!"


def test_usage_ledger_append_only(tmp_path):
    """Verifies that usage_ledger is append-only: UPDATE and DELETE are prohibited by SQLite triggers."""
    import sqlite3
    from backend.storage import init_db, record_usage

    test_db = tmp_path / "test_ledger.db"
    init_db(test_db)

    # Insert a record
    record_usage(
        purpose="test_purpose",
        model_id="muse-spark-1.3",
        usage={"total_tokens": 100},
        incident_id="INC-TEST",
        db_path=test_db,
    )

    conn = sqlite3.connect(test_db)

    # 1. Verify UPDATE fails
    with pytest.raises(sqlite3.IntegrityError, match="append-only: updates are prohibited"):
        conn.execute("UPDATE usage_ledger SET estimated_cost_usd = 999.0 WHERE incident_id = 'INC-TEST'")

    # 2. Verify DELETE fails
    with pytest.raises(sqlite3.IntegrityError, match="append-only: deletes are prohibited"):
        conn.execute("DELETE FROM usage_ledger WHERE incident_id = 'INC-TEST'")

    conn.close()

