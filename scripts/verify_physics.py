"""
verify_physics.py — prints the verification table (analytic vs numerical) of physics/verification.py.
The same comparisons are checked automatically by `pytest` (tests/test_verification.py); this script
shows the numbers in a readable form for the report.

Run from the project folder:   python scripts/verify_physics.py
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):          # Γ, θ, ∮ on any Windows console / redirect
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics.verification import format_table, verification_checks  # noqa: E402

if __name__ == "__main__":
    checks = verification_checks()
    print(format_table(checks))
    sys.exit(0 if all(c.ok for c in checks) else 1)
