"""The verification table of the report (physics/verification.py): every comparison with the analytic
solution of the course holds to round-off."""
import pytest

from physics.verification import TOLERANCE, format_table, verification_checks


def test_every_verification_check_holds():
    checks = verification_checks()
    assert len(checks) >= 30
    bad = [c for c in checks if not c.ok]
    assert not bad, format_table(bad)


def test_table_lists_every_check():
    checks = verification_checks()
    text = format_table(checks)
    assert text.count("\n") == len(checks) + 3 and text.endswith("->  OK")
    assert all(c.error < TOLERANCE for c in checks)
    assert any("L' = ρ V∞ Γ" in c.quantity and c.analytic == pytest.approx(1.225 * 2.0) for c in checks)
