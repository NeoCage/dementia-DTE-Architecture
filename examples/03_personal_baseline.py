"""Principle P1: compare the patient to themselves, not to a population.

The same gait speed is unremarkable for one person and alarming for another. This is the property
that makes the object a Digital Twin rather than a dashboard.

Run: PYTHONPATH=src python examples/03_personal_baseline.py
"""

from datetime import datetime, timedelta, timezone

from dte.models.decline import DeviationDetector
from dte.twin import Baseline

print(__doc__.splitlines()[0])
print("=" * 88)

start = datetime.now(timezone.utc) - timedelta(days=45)


def build(label: str, typical: float) -> Baseline:
    b = Baseline()
    for i in range(35):
        b.update({"gait_speed_ms": typical + 0.02 * ((-1) ** i)}, at=start + timedelta(days=i))
    print(
        f"  {label:<22} baseline median = {b.stats['gait_speed_ms'].median:.2f} m/s  "
        f"(n={b.n_observations}, established={b.is_established})"
    )
    return b


print("\nTwo patients, each observed for 35 days:")
slow = build("habitually slower", 0.95)
fast = build("habitually faster", 1.42)

observed = 0.95
print(f"\nBoth are now measured at {observed:.2f} m/s. The same number:")
for label, b in (("habitually slower", slow), ("habitually faster", fast)):
    z = b.deviation("gait_speed_ms", observed)
    r = DeviationDetector().evaluate("gait_speed_ms", [observed] * 4, b)
    flag = "ALERT" if r.deviated else "normal for this person"
    print(f"  {label:<22} robust z = {z:+6.2f}   -> {flag}")

print("\nA population threshold would have treated these two identically.")

# --------------------------------------------------------------- the week-one guarantee
print("\n" + "-" * 88)
print("SAFETY PROPERTY: no alert can fire before the baseline is established.\n")
new = Baseline()
for i in range(3):
    new.update({"gait_speed_ms": 1.10}, at=datetime.now(timezone.utc) - timedelta(days=3 - i))
r = DeviationDetector().evaluate("gait_speed_ms", [0.60] * 4, new)
print("  New patient, 3 days of data, measured at 0.60 m/s (a dramatic drop)")
print(f"  deviated = {r.deviated}")
print(f"  {r.detail}")

print("\n" + "=" * 88)
print("""
Alerting against an unestablished baseline is how monitoring pilots generate noise in week one and
get abandoned in week six. The minimum observation period is enforced in code, not in a runbook.

  docs/03-digital-twin-engine.md  §3.1
  docs/01-architecture-overview.md  Principle P1
""")
