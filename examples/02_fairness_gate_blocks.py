"""The subgroup fairness gate: two independent ways to block a release.

The second one is the one usually missed: a PERFECTLY ACCURATE model is still blocked if a subgroup
is too small to certify. Shipping uncertified and assuming it is fine is how gaps reach production.

Run: PYTHONPATH=src python examples/02_fairness_gate_blocks.py
"""

import numpy as np

from dte.fairness.subgroup import evaluate_fairness

print(__doc__.splitlines()[0])
print("=" * 88)

# ---------------------------------------------------------------- Case 1: measured gap
print("\nCASE 1 — a measured accuracy gap between subgroups")
y_true = np.array([1, 0] * 60)
y_pred = np.array([1, 0] * 45 + [0, 1] * 15)  # group B predicted wrongly far more often
groups = ["majority-group"] * 90 + ["under-represented-group"] * 30
r1 = evaluate_fairness(y_true, y_pred, {"race_ethnicity": groups})
print(f"  {r1.summary()}")
for s in r1.subgroups:
    acc = f"{s.accuracy:.1%}" if s.accuracy is not None else "n/a"
    print(f"    {s.group:<26} n={s.n:<4} accuracy={acc}")
for b in r1.blocking_reasons:
    print(f"  BLOCKED: {b}")

# ---------------------------------------------------------------- Case 2: cannot certify
print("\nCASE 2 — a PERFECT model, blocked because a subgroup cannot be certified")
y_true = np.array([1, 0] * 50)
y_pred = y_true.copy()  # 100% accurate
groups = ["majority-group"] * 95 + ["under-represented-group"] * 5
r2 = evaluate_fairness(y_true, y_pred, {"race_ethnicity": groups})
print(f"  population accuracy = {r2.population_accuracy:.1%}  (a flawless model)")
print(f"  {r2.summary()}")
for b in r2.blocking_reasons:
    print(f"  BLOCKED: {b}")
print("  REMEDIATION:")
for m in r2.remediation:
    print(f"    - {m}")

# ---------------------------------------------------------------- Case 3: passes
print("\nCASE 3 — equal performance across adequately sized subgroups")
y_true = np.array([1, 0] * 60)
groups = ["majority-group"] * 60 + ["under-represented-group"] * 60
r3 = evaluate_fairness(y_true, y_true.copy(), {"race_ethnicity": groups})
print(f"  {r3.summary()}")

print("\n" + "=" * 88)
print("""
Why "cannot certify" must block:

If a subgroup cannot be evaluated, the honest position is that the model's behaviour on that group
is UNKNOWN — not that it is fine. The alternative to blocking is narrowing the model's documented
intended population IN WRITING, so the limitation is visible to every clinician who uses it.

The gap closes through deliberate rebalancing and explicit fairness constraints, not by waiting for
a bigger dataset. Datasets getting bigger has not historically closed these gaps.

  docs/07-validation-and-benchmarks.md  §7.4
  docs/adr/0007-subgroup-fairness-gate.md
""")
