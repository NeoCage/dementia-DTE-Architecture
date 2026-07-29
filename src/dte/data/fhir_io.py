"""Minimal FHIR R5 serialisation for the reference implementation.

Implements the mappings documented in ``docs/05-data-architecture.md`` §5.2 and
``docs/adr/0001-fhir-r5-canonical-model.md``.

SCOPE
-----
This is a *demonstration* of the two mappings that carry architectural weight, not a full FHIR
implementation. A real deployment uses a proper FHIR server and validates against published
profiles. In particular this module does not validate, does not handle references properly, and
does not implement search.

THE TWO MAPPINGS THAT MATTER
----------------------------
* A risk score becomes a **RiskAssessment**, not an Observation, because ``RiskAssessment.basis``
  is designed to carry the evidence a prediction rests on. The consequence is that the explanation
  travels with the score into any FHIR-conformant system rather than living only in our own UI.
* A delivered cue becomes a **Procedure**, because it is an intervention performed on a patient and
  must be visible to audit as something that happened TO them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

TEST_SECURITY_LABEL = {
    "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
    "code": "HTEST",
    "display": "test health data",
}
LOCAL_CS = "https://example.org/dte/CodeSystem/dte"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _meta() -> dict[str, Any]:
    """Every resource this module emits is labelled as synthetic test data."""
    return {"security": [TEST_SECURITY_LABEL]}


def risk_output_to_fhir(
    patient_id: str,
    risk: Any,
    basis_references: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Serialise a :class:`dte.models.risk.RiskOutput` as a FHIR R5 RiskAssessment.

    The explanation is written into ``note`` and the supporting resources into ``basis``, so the
    reasoning cannot be separated from the score.
    """
    d = risk.to_dict()
    explanation_lines = [
        f"{i + 1}) {f['name']}: contribution {f['contribution']}, {f['direction']}"
        f" — {f['plain_language']}"
        for i, f in enumerate(d["top_features"])
    ]

    return {
        "resourceType": "RiskAssessment",
        "meta": _meta(),
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": LOCAL_CS,
                    "code": "mci-to-dementia-conversion-risk",
                    "display": (
                        f"MCI to dementia conversion risk, {d['window_months']} month window"
                    ),
                }
            ]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "occurrenceDateTime": _now_iso(),
        "performer": {"display": f"Digital Twin Engine risk service {d['model_version']}"},
        "basis": [{"reference": r} for r in (basis_references or [])],
        "prediction": [
            {
                "outcome": {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "code": "52448006",
                            "display": "Dementia",
                        }
                    ]
                },
                "probabilityDecimal": d["score"],
                "qualitativeRisk": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/risk-probability",
                            "code": d["band"],
                        }
                    ]
                },
                "rationale": "; ".join(explanation_lines[:3])
                + ". THIS IS A RISK ESTIMATE, NOT A DIAGNOSIS.",
            }
        ],
        "note": [
            {"text": "EXPLANATION — ranked contributing features: " + " ".join(explanation_lines)},
            {
                "text": (
                    f"MODEL PROVENANCE — version={d['model_version']}; "
                    f"brier={d['brier_score']}; "
                    f"max_subgroup_gap_at_release={d['max_subgroup_gap_at_release']}"
                )
            },
            {"text": "PATIENT-FACING VERSION — " + risk.patient_facing_summary()},
            {"text": "ALL VALUES SYNTHETIC. Not a real assessment for a real person."},
        ],
    }


def cue_to_fhir(
    patient_id: str,
    decision: Any,
    selection: Any,
    content_id: str,
    latency_s: float,
    response: Optional[str] = None,
    reward: Optional[float] = None,
) -> dict[str, Any]:
    """Serialise a delivered cue as a FHIR R5 Bundle: Procedure plus response Observation."""
    procedure = {
        "resourceType": "Procedure",
        "meta": _meta(),
        "status": "completed",
        "category": {"text": "Non-pharmacological cognitive intervention"},
        "code": {
            "coding": [
                {
                    "system": LOCAL_CS,
                    "code": "memory-anchor-cue",
                    "display": "Personalised memory anchoring cue",
                }
            ],
            "text": f"Memory anchoring cue, {selection.arm.value} modality",
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "occurrenceDateTime": _now_iso(),
        "performer": [{"actor": {"display": "Memory Anchoring Pipeline, on-device, autonomous"}}],
        "reasonCode": [{"text": decision.reason}],
        "note": [
            {"text": "DECISION TRACE — " + decision.explain()},
            {"text": "ARM SELECTION — " + selection.explain()},
            {"text": f"CONTENT — content_id={content_id}"},
            {"text": f"DELIVERY — latency {latency_s:.2f} s (target < 2.0 s p95); single cue only"},
            {
                "text": (
                    "WHY A Procedure RESOURCE: this is an intervention performed on a patient, "
                    "delivered autonomously to a cognitively vulnerable person, and must be "
                    "visible to audit as something that happened TO them."
                )
            },
        ],
    }

    entries: list[dict[str, Any]] = [{"resource": procedure}]

    if response is not None:
        obs: dict[str, Any] = {
            "resourceType": "Observation",
            "meta": _meta(),
            "status": "final",
            "code": {
                "coding": [{"system": LOCAL_CS, "code": "cue-response"}],
                "text": "Cue response",
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": _now_iso(),
            "valueCodeableConcept": {"coding": [{"system": LOCAL_CS, "code": response}]},
            "component": [],
            "note": [
                {
                    "text": (
                        "REWARD ASYMMETRY — recalled=+1.0, engaged=+0.3, ignored=0.0, "
                        "DISTRESSED=-2.0. Upsetting someone is worse than failing to help them."
                    )
                }
            ],
        }
        if reward is None:
            obs["component"].append(
                {
                    "code": {"text": "Assigned reward"},
                    "dataAbsentReason": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/data-absent-reason",
                                "code": "not-asked-yet",
                            }
                        ]
                    },
                }
            )
            obs["note"].append(
                {
                    "text": (
                        "MISSING DATA — recorded as absent, NOT imputed as success. Systems that "
                        "impute missing feedback as positive learn to fire constantly."
                    )
                }
            )
        else:
            obs["component"].append(
                {
                    "code": {"text": "Assigned reward"},
                    "valueQuantity": {"value": reward, "unit": "reward"},
                }
            )
        entries.append({"resource": obs})

    return {
        "resourceType": "Bundle",
        "meta": _meta(),
        "type": "collection",
        "timestamp": _now_iso(),
        "entry": entries,
    }
