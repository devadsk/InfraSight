"""
Referential integrity test suite for pytest.
Runs validate_all() to guarantee zero broken references across scenarios,
devices, telemetry, manuals, images, and diagnostics.
"""

from scripts.validate_data import validate_all


def test_referential_integrity():
    passed = validate_all()
    assert passed is True, "Referential integrity validation failed!"
