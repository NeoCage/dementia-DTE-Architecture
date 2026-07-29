"""FastAPI demonstration server for the Digital Twin Engine.

⚠️  **DO NOT DEPLOY THIS.**

This server implements NO authentication, NO authorisation, NO TLS, NO encryption at rest, NO audit
logging and NO consent enforcement. It exists to make the architecture concrete and explorable on
``localhost``. Every one of those controls is specified in
``docs/08-security-and-privacy.md`` and would have to be built before any real data touched it.
See §8.9 for the explicit list of what is missing.

All data is synthetic, generated at request time.

Run with::

    make api
    # then open http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from dte import __version__
from dte.config import DEFAULT_CONFIG
from dte.data.fhir_io import risk_output_to_fhir
from dte.data.synthetic import generate_cohort, generate_day, generate_eeg, generate_rr_intervals
from dte.fairness.subgroup import evaluate_fairness
from dte.fusion.detector import FusionInput, OpportunityDetector
from dte.models.decline import forecast_trajectory
from dte.models.risk import RiskModel
from dte.policy.cue_selector import CueSelector, Response
from dte.signals.eeg import extract_eeg_features
from dte.signals.hrv import extract_hrv_features

app = FastAPI(
    title="Dementia Digital Twin Engine — reference implementation",
    version=__version__,
    description=(
        "⚠️ NOT A MEDICAL DEVICE. NOT FOR DEPLOYMENT. No authentication, no encryption, no audit "
        "logging, no consent enforcement. All data is SYNTHETIC and generated at request time. "
        "Every numeric result is ILLUSTRATIVE and must not be cited as a clinical finding. "
        "See DISCLAIMER.md."
    ),
)

# Module-level singletons so the demo has continuity across requests.
_model: Optional[RiskModel] = None
_selectors: dict[str, CueSelector] = {}


def _get_model() -> RiskModel:
    """Train the ensemble on synthetic data, and run the fairness gate before serving it."""
    global _model
    if _model is None:
        cohort = generate_cohort(n=600, seed=42)
        X, y, attributes = cohort.to_arrays()
        split = int(0.75 * len(y))
        m = RiskModel().fit(X[:split], y[:split], cohort.feature_names)

        y_pred = m.model.predict(X[split:])
        report = evaluate_fairness(y[split:], y_pred, {k: v[split:] for k, v in attributes.items()})
        m.max_subgroup_gap_at_release = report.max_gap
        proba = m.model.predict_proba(X[split:])[:, 1]
        m.brier_score = float(np.mean((proba - y[split:]) ** 2))
        _model = m
    return _model


# ----------------------------------------------------------------------------- schemas


class OpportunityRequest(BaseModel):
    """Input to the Memory Anchoring Pipeline's fast loop."""

    patient_id: str = Field("demo-001", description="Pseudonymous identifier only")
    place_class: str = Field(
        "known-significant", pattern="^(home|known-significant|known-routine|novel|unknown)$"
    )
    place_significance: Optional[float] = Field(None, ge=0.0, le=1.0)
    hour_of_day: int = Field(14, ge=0, le=23)
    agitation_index: Optional[float] = Field(0.24, ge=0.0, le=1.0)
    theta_alpha_z: Optional[float] = Field(
        1.8, description="Deviation vs this patient's OWN baseline"
    )
    eligible_content_count: int = Field(3, ge=0)
    signal_quality: float = Field(0.82, ge=0.0, le=1.0)
    minutes_since_last_cue: Optional[float] = Field(71.0, ge=0.0)
    cues_delivered_today: int = Field(3, ge=0)
    consent_permits_cue: bool = Field(True, description="Includes the patient stop-command check")


class TrajectoryRequest(BaseModel):
    times_months: list[float] = Field([0.0, 6.0, 12.0])
    values: list[float] = Field([26.0, 24.5, 23.0])
    horizon_months: float = Field(12.0, gt=0)
    metric: str = "moca_total"


class ResponseReport(BaseModel):
    patient_id: str = "demo-001"
    place_class: str = "known-significant"
    hour_of_day: int = Field(14, ge=0, le=23)
    arm: str = "photo"
    response: str = Field("engaged-no-confirmed-recall")


# ----------------------------------------------------------------------------- routes


@app.get("/", tags=["meta"])
def root() -> dict[str, Any]:
    return {
        "name": "Dementia Digital Twin Engine — reference implementation",
        "version": __version__,
        "warning": (
            "NOT A MEDICAL DEVICE. NOT FOR DEPLOYMENT. No auth, no TLS, no encryption, no audit "
            "log, no consent enforcement. All data synthetic. All results ILLUSTRATIVE."
        ),
        "docs": "/docs",
        "read_first": "DISCLAIMER.md",
        "architecture": "docs/01-architecture-overview.md",
    }


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "data": "synthetic-only"}


@app.post("/predict/opportunity", tags=["memory anchoring"])
def predict_opportunity(req: OpportunityRequest) -> dict[str, Any]:
    """Fast loop: is now a memory-retrieval opportunity?

    Returns a decision whether or not a cue is delivered. **Silence is a first-class outcome** and
    is returned with its reason (docs/04). Note that agitation acts as a hard veto: a high
    ``agitation_index`` blocks delivery even when confidence is well above threshold.
    """
    detector = OpportunityDetector(
        threshold=DEFAULT_CONFIG.opportunity_threshold,
        agitation_veto=DEFAULT_CONFIG.agitation_veto,
        daily_budget=DEFAULT_CONFIG.daily_cue_budget,
        refractory_minutes=DEFAULT_CONFIG.refractory_minutes,
    )
    decision = detector.decide(FusionInput(**req.model_dump(exclude={"patient_id"})))

    out: dict[str, Any] = {
        "deliver": decision.deliver,
        "confidence": round(decision.confidence, 4),
        "threshold": decision.threshold,
        "channel_scores": {k: round(v, 4) for k, v in decision.channel_scores.items()},
        "gates": [{"name": g.name, "passed": g.passed, "detail": g.detail} for g in decision.gates],
        "failed_gates": decision.failed_gates,
        "reason": decision.reason,
        "trace": decision.explain(),
    }

    if decision.deliver:
        sel = _selectors.setdefault(req.patient_id, CueSelector(seed=7))
        selection = sel.select(req.place_class, req.hour_of_day)
        if selection:
            out["selection"] = {
                "arm": selection.arm.value,
                "exploratory": selection.exploratory,
                "arm_value": round(selection.arm_value, 4),
                "arm_n": selection.arm_n,
                "context_key": selection.context_key,
                "alternatives": {
                    k: {"value": round(v, 4), "n": n}
                    for k, (v, n) in selection.alternatives.items()
                },
                "trace": selection.explain(),
            }
    return out


@app.post("/report/response", tags=["memory anchoring"])
def report_response(req: ResponseReport) -> dict[str, Any]:
    """Report an observed patient response, updating the per-patient policy.

    ``response="unknown"`` is recorded as MISSING and returns ``reward: null`` — it is never
    imputed as success (docs/04 §4.6).
    """
    try:
        resp = Response(req.response)
    except ValueError as exc:
        raise HTTPException(422, f"unknown response value: {req.response}") from exc

    sel = _selectors.setdefault(req.patient_id, CueSelector(seed=7))
    selection = sel.select(req.place_class, req.hour_of_day)
    if selection is None:
        raise HTTPException(409, "no cue arm currently available (all suppressed)")
    reward = sel.update(selection, resp)

    return {
        "response": resp.value,
        "reward": reward,
        "reward_note": (
            "null means MISSING, not zero. Missing caregiver confirmation is never imputed as "
            "success."
            if reward is None
            else (
                "distress is weighted -2.0 against +1.0 for recall: the policy is "
                "biased toward silence."
            )
        ),
        "policy_snapshot": sel.snapshot(),
    }


@app.get("/predict/risk", tags=["risk"])
def predict_risk(patient_index: int = 0) -> dict[str, Any]:
    """Slow loop: MCI-to-dementia risk for one synthetic patient.

    The score is returned with its ranked reasoning. It is architecturally impossible to get a
    score without one (ADR-0006).
    """
    model = _get_model()
    cohort = generate_cohort(n=600, seed=42)
    if not 0 <= patient_index < len(cohort.patients):
        raise HTTPException(404, f"patient_index must be in [0, {len(cohort.patients) - 1}]")

    p = cohort.patients[patient_index]
    risk = model.predict(p.features)
    return {
        "patient_id": p.patient_id,
        "ground_truth_converter": p.converter,
        "risk": risk.to_dict(),
        "patient_facing_summary": risk.patient_facing_summary(),
        "fhir": risk_output_to_fhir(
            p.patient_id, risk, [f"Observation/synthetic-eeg-{patient_index}"]
        ),
        "warning": "ILLUSTRATIVE. Model trained on synthetic data. Not a clinical result.",
    }


@app.post("/simulate/decline", tags=["risk"])
def simulate_decline(req: TrajectoryRequest) -> dict[str, Any]:
    """Project a cognitive trajectory with mandatory uncertainty.

    Try it with only two observations: the point estimate is **suppressed** because the interval is
    too wide to be actionable (docs/03 §3.4).
    """
    f = forecast_trajectory(
        req.times_months, req.values, horizon_months=req.horizon_months, metric=req.metric
    )
    return {
        "forecast": f.to_dict(),
        "note": (
            "The point estimate is suppressed when the confidence interval is too wide to be "
            "actionable. A confident-looking forecast the model cannot support does lasting "
            "damage to clinical trust."
        ),
    }


@app.get("/fairness/report", tags=["governance"])
def fairness_report(noise_multiplier: float = 2.5) -> dict[str, Any]:
    """Run the subgroup fairness gate.

    Try ``noise_multiplier=1.0`` for a fair cohort (gate passes) and ``2.5`` for one with an
    under-represented, noisier group (gate blocks). This is the gate that has unconditional
    release-blocking authority (ADR-0007).
    """
    cohort = generate_cohort(n=600, underrepresented_noise_multiplier=noise_multiplier, seed=42)
    X, y, attributes = cohort.to_arrays()
    split = int(0.75 * len(y))
    m = RiskModel().fit(X[:split], y[:split], cohort.feature_names)
    y_pred = m.model.predict(X[split:])
    report = evaluate_fairness(y[split:], y_pred, {k: v[split:] for k, v in attributes.items()})
    return {"summary": report.summary(), "report": report.to_dict()}


@app.get("/signals/demo", tags=["signals"])
def signals_demo(artefact_rate: float = 0.15, agitated: bool = False) -> dict[str, Any]:
    """Run the edge signal pipeline on a synthetic recording.

    Raise ``artefact_rate`` above roughly 0.4 and the quality gate fails: the pipeline returns
    ``quality="insufficient"`` and the caller must NOT infer. Features are never imputed.
    """
    raw, motion = generate_eeg(artefact_rate=artefact_rate, rng=np.random.default_rng(3))
    eeg = extract_eeg_features(raw, motion_mask=motion)
    hrv = extract_hrv_features(
        generate_rr_intervals(agitated=agitated, rng=np.random.default_rng(3))
    )
    return {
        "eeg": {
            "quality": eeg.quality,
            "usable_epoch_fraction": round(eeg.usable_epoch_fraction, 4),
            "valid_channel_count": eeg.valid_channel_count,
            "relative_power": {
                k: (round(v, 4) if v is not None else None) for k, v in eeg.relative_power.items()
            },
            "theta_alpha_ratio": round(eeg.theta_alpha_ratio, 4) if eeg.theta_alpha_ratio else None,
            "is_usable": eeg.is_usable,
        },
        "hrv": {
            "quality": hrv.quality,
            "rmssd_ms": round(hrv.rmssd_ms, 2) if hrv.rmssd_ms else None,
            "lf_hf_ratio": round(hrv.lf_hf_ratio, 3) if hrv.lf_hf_ratio else None,
            "agitation_index": round(hrv.agitation_index, 3) if hrv.agitation_index else None,
            "vetoes_cue": (hrv.agitation_index or 0) > DEFAULT_CONFIG.agitation_veto,
        },
        "note": (
            "Raw EEG existed only inside this request and was discarded after feature extraction. "
            "There is no code path that persists or transmits it (ADR-0002)."
        ),
    }


@app.get("/day/simulate", tags=["memory anchoring"])
def day_simulate(seed: int = 42) -> dict[str, Any]:
    """Simulate a full day of MAP decisions — the same trace as ``make demo``."""
    detector = OpportunityDetector()
    sel = CueSelector(seed=seed)
    events = generate_day(seed=seed)
    log: list[dict[str, Any]] = []
    delivered = 0
    last_cue_min: Optional[float] = None

    for e in events:
        now_min = e.hour * 60 + e.minute
        inp = FusionInput(
            place_class=e.place_class,
            place_significance=e.place_significance,
            hour_of_day=e.hour,
            agitation_index=0.82 if e.agitated else 0.24,
            theta_alpha_z=float(np.random.default_rng(now_min).normal(1.0, 0.8)),
            eligible_content_count=e.eligible_content_count,
            signal_quality=0.82,
            minutes_since_last_cue=None if last_cue_min is None else now_min - last_cue_min,
            cues_delivered_today=delivered,
            consent_permits_cue=True,
        )
        d = detector.decide(inp)
        entry = {
            "time": f"{e.hour:02d}:{e.minute:02d}",
            "place": e.place_class,
            "trace": d.explain(),
        }
        if d.deliver:
            s = sel.select(e.place_class, e.hour)
            if s:
                entry["arm"] = s.arm.value
                delivered += 1
                last_cue_min = now_min
        log.append(entry)

    return {
        "events": log,
        "cues_delivered": delivered,
        "evaluations": len(events),
        "silence_rate": round(1 - delivered / len(events), 3),
        "note": (
            "Silence is the default and the majority outcome. The system is precision-weighted: "
            "built to miss opportunities rather than fire wrongly."
        ),
    }
