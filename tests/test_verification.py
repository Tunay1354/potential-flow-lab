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
    assert any("L′ = ρ V∞ Γ_cw" in c.quantity and c.analytic == pytest.approx(1.225 * 2.0) for c in checks)


def test_scene_checks_skip_scenes_that_are_not_a_cylinder():
    """A doublet turned against the free stream (or a vortex off its center) is no cylinder: no cylinder
    rows and no error (before: the missing closed body raised ValueError)."""
    from physics import Doublet, Uniform, Vortex
    from physics.program_checks import scene_checks
    view = ((-4.0, 4.0), (-3.0, 3.0))
    assert scene_checks("turned", [Uniform(), Doublet(mu=1.0, delta=30.0)], view) == []
    assert scene_checks("off center", [Uniform(), Doublet(mu=1.0), Vortex(Gamma=-2.0, x0=0.5)], view) == []
    rows = scene_checks("rotated cylinder", [Uniform(alpha=30.0), Doublet(mu=1.0, delta=30.0)], view)
    assert rows and all(r.ok for r in rows)
