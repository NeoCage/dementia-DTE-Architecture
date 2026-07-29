"""A risk score serialised as FHIR R5, with its explanation travelling in `basis`.

The mapping choice matters: RiskAssessment.basis is designed to hold the evidence a prediction
rests on. Using it means the explanation cannot be separated from the score — if the score is
exported to another system, the reasoning goes with it.

Run: PYTHONPATH=src python examples/04_fhir_round_trip.py
"""

import json

import numpy as np

from dte.data.fhir_io import risk_output_to_fhir
from dte.data.synthetic import generate_cohort
from dte.fairness.subgroup import evaluate_fairness
from dte.models.risk import RiskModel

print(__doc__.splitlines()[0])
print("=" * 88)

cohort = generate_cohort(n=400, seed=42)
X, y, attributes = cohort.to_arrays()
split = int(0.75 * len(y))

model = RiskModel().fit(X[:split], y[:split], cohort.feature_names)
report = evaluate_fairness(
    y[split:], model.model.predict(X[split:]), {k: v[split:] for k, v in attributes.items()}
)
model.max_subgroup_gap_at_release = report.max_gap
proba = model.model.predict_proba(X[split:])[:, 1]
model.brier_score = float(np.mean((proba - y[split:]) ** 2))

print(f"\nFairness gate before serving any score: {report.summary()}")

patient = cohort.patients[3]
risk = model.predict(patient.features)

print(f"\nScore for {patient.patient_id}: {risk.score:.3f} ({risk.band})")
print("Ranked reasoning (a score cannot be constructed without >= 3 of these):")
for i, f in enumerate(risk.top_features, 1):
    print(f"  {i}. {f.name:<26} {f.contribution:+.4f}  {f.direction:<16} {f.plain_language}")

print("\nAttempting to construct a score with too few features:")
from dte.models.risk import Explanation, RiskOutput  # noqa: E402

try:
    RiskOutput(
        score=0.7,
        band="elevated",
        top_features=[Explanation("theta_relative_power", 0.2, "increases-risk")],
    )
except ValueError as exc:
    print(f"  refused: {exc}")

fhir = risk_output_to_fhir(
    patient.patient_id, risk, ["Observation/synthetic-eeg-001", "Observation/synthetic-moca-001"]
)

print("\nFHIR R5 RiskAssessment:")
print(f"  resourceType   = {fhir['resourceType']}")
print(f"  probability    = {fhir['prediction'][0]['probabilityDecimal']}")
print(f"  basis          = {[b['reference'] for b in fhir['basis']]}")
print(f"  security label = {fhir['meta']['security'][0]['code']} (synthetic test data)")
print(f"  notes attached = {len(fhir['note'])}")

print("\nPatient-facing summary carried in the same resource:")
print("  " + risk.patient_facing_summary().replace(". ", ".\n  "))

print("\nFull resource:")
print(json.dumps(fhir, indent=2)[:1400] + "\n  ... (truncated)")

print("\n" + "=" * 88)
print("""
  docs/05-data-architecture.md  §5.2
  docs/adr/0001-fhir-r5-canonical-model.md
  docs/adr/0006-explainability-as-a-hard-requirement.md
""")
