"""The evaluation path that composes the twin into a working engine.

WHY THIS MODULE EXISTS
----------------------
Until this module, the architecture's components were individually implemented and
individually tested, and nothing composed them. ``TwinState`` was constructed by its own
tests and by nothing else; ``detect_tier`` and ``assert_claim_permitted`` were called by
tests and by nothing else. A reviewer could verify that each mechanism worked and still
not be able to verify that the system did.

That gap mattered more than a missing integration usually does, because the central claim
of this architecture is a claim about *composition*: that a twin may not emit a claim above
the ceiling of the tier it is operating at **right now**. A ceiling enforced in a unit test
is a ceiling enforced on a function. A ceiling enforced here is a ceiling enforced on the
system, because this module is the only path by which a claim reaches a caller.

THE INVARIANT
-------------
Every emission leaves through :meth:`TwinEngine._guarded`. That method calls
``assert_claim_permitted`` before the payload is computed, and there is no second exit.
Delete the call and the end-to-end suite fails — which is the point, and is what
``tests/test_engine.py`` exists to demonstrate.

THREE PROPERTIES THAT ONLY EXIST AT THIS LAYER
----------------------------------------------
*Tier is derived per evaluation, from what actually arrived.* Not from enrolment, not from
configuration. A household enrolled with a headband that stops wearing it is a T2 household
on the next evaluation, and the engine says so.

*Consent gates reads, so withdrawing it lowers the tier.* Because a modality the patient has
not consented to is not read, it is not available, and an unavailable signal cannot support a
tier. Revoking neural consent therefore drops a T3 twin to T2 and makes cue claims
impermissible — not by a separate consent check bolted onto the cue path, but as a
consequence of the ladder itself.

*Silence is a return value.* Suppressions are first-class, carry a reason code, and are
returned alongside emissions rather than being logged and discarded. "Why did nothing
happen?" is the question an operator actually asks, and it has an answer here.

See ``docs/03-digital-twin-engine.md`` and ``docs/15-fidelity-ladder.md``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from dte.config import STALE_AFTER_HOURS
from dte.fusion.detector import (
    Alert,
    AlertBudget,
    FusionInput,
    OpportunityDetector,
)
from dte.models.decline import DeviationDetector
from dte.policy.cue_selector import CueSelector
from dte.tiers import (
    AttributionBasis,
    Claim,
    ClaimCeilingViolation,
    TierState,
    assert_claim_permitted,
    detect_tier,
    downgrade_note,
)
from dte.twin import TwinState

# Signal family -> the consent attribute that must be true before it may be READ.
# A family with no entry here needs no specific consent beyond enrolment.
_CONSENT_FOR_SIGNAL: dict[str, str] = {
    "phone_ambient": "location_data",
    "wristband": "wearable_physiology",
    "eeg": "neural_data",
}

# How many recent values the engine keeps per feature for change detection.
_HISTORY = 60


class Reason:
    """Reason codes for suppression. Stable strings — they end up in audit records."""

    CEILING = "CLAIM_CEILING"
    BASELINE = "BASELINE_NOT_ESTABLISHED"
    STALE = "STATE_STALE"
    CONSENT = "CONSENT_WITHHELD"
    QUALITY = "SIGNAL_QUALITY"
    NO_DEVIATION = "NO_DEVIATION"
    NO_MODEL = "MODEL_NOT_AVAILABLE"
    BUDGET = "ALERT_BUDGET"
    DETECTOR = "DETECTOR_DECLINED"
    NO_CONTENT = "NO_ELIGIBLE_CONTENT"


@dataclass(frozen=True)
class Observation:
    """One arrival of data about one household, at one moment.

    A family that is absent or empty did not arrive. That is the whole input to tier
    derivation: the engine never asks what the patient was enrolled with.
    """

    patient_id: str
    at: datetime
    caregiver_report: Optional[dict[str, Any]] = None
    phone_ambient: Optional[dict[str, Optional[float]]] = None
    wristband: Optional[dict[str, Optional[float]]] = None
    eeg: Optional[dict[str, Optional[float]]] = None
    signal_quality: float = 1.0
    attribution: AttributionBasis = AttributionBasis.A0_NONE
    # Cue context, used only if the twin reaches T3 and consent permits.
    place_class: str = "unknown"
    place_significance: Optional[float] = None
    eligible_content_count: int = 0
    source: str = "ingest"
    device_id: Optional[str] = None


@dataclass(frozen=True)
class Emission:
    claim: Claim
    payload: dict[str, Any]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim.name,
            "claim_label": self.claim.label,
            "payload": self.payload,
            "explanation": self.explanation,
        }


@dataclass(frozen=True)
class Suppression:
    claim: Claim
    reason: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"claim": self.claim.name, "reason": self.reason, "detail": self.detail}


@dataclass
class EvaluationResult:
    """What one evaluation produced, and what it refused to produce."""

    patient_id: str
    evaluated_at: datetime
    tier_state: TierState
    emissions: list[Emission] = field(default_factory=list)
    suppressions: list[Suppression] = field(default_factory=list)
    downgrade: Optional[str] = None
    stale: bool = False
    provenance_index: Optional[int] = None

    @property
    def silent(self) -> bool:
        return not self.emissions

    def emitted(self, claim: Claim) -> bool:
        return any(e.claim is claim for e in self.emissions)

    def suppression_for(self, claim: Claim) -> Optional[Suppression]:
        return next((s for s in self.suppressions if s.claim is claim), None)

    def explain(self) -> str:
        head = f"[{self.evaluated_at.isoformat(timespec='seconds')}] {self.tier_state.explain()}"
        if self.downgrade:
            head += f"\n  DOWNGRADE: {self.downgrade}"
        if self.stale:
            head += "\n  STALE: no data within the freshness window; claims withheld."
        for e in self.emissions:
            head += f"\n  EMIT    {e.claim.name}: {e.explanation}"
        for s in self.suppressions:
            head += f"\n  SILENT  {s.claim.name}: {s.reason} {s.detail}".rstrip()
        return head

    def to_dict(self) -> dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "tier": self.tier_state.to_dict(),
            "downgrade": self.downgrade,
            "stale": self.stale,
            "emissions": [e.to_dict() for e in self.emissions],
            "suppressions": [s.to_dict() for s in self.suppressions],
            "provenance_index": self.provenance_index,
        }


class TwinEngine:
    """Composes the twin, the ladder and the models into one evaluation path.

    The engine owns no clinical logic of its own. Every decision it makes is delegated to a
    component that is separately tested; what the engine contributes is the *order* in which
    they run and the single gate they all pass through.
    """

    def __init__(
        self,
        twin: TwinState,
        *,
        deviation_detector: Optional[DeviationDetector] = None,
        opportunity_detector: Optional[OpportunityDetector] = None,
        cue_selector: Optional[CueSelector] = None,
        alert_budget: Optional[AlertBudget] = None,
        risk_model: Optional[Any] = None,
        deviation_features: Optional[list[str]] = None,
    ) -> None:
        self.twin = twin
        self.deviation_detector = deviation_detector or DeviationDetector()
        self.opportunity_detector = opportunity_detector or OpportunityDetector()
        self.cue_selector = cue_selector or CueSelector()
        self.alert_budget = alert_budget or AlertBudget()
        self.risk_model = risk_model
        self.deviation_features = deviation_features or ["gait_speed"]

        self._history: dict[str, deque[float]] = {}
        self._last_tier: Optional[TierState] = None
        self._last_cue_at: Optional[datetime] = None
        self._cues_today: dict[str, int] = {}

    # ------------------------------------------------------------------ gate
    def _guarded(
        self,
        claim: Claim,
        tier_state: TierState,
        result: EvaluationResult,
        build: Callable[[], Optional[tuple[dict[str, Any], str]]],
    ) -> None:
        """The only path by which a claim leaves this engine.

        The ceiling is checked BEFORE the payload is computed, so an impermissible claim is
        never even calculated, let alone returned. ``build`` returns None to decline for a
        reason of its own, having already recorded the suppression.
        """
        try:
            assert_claim_permitted(tier_state, claim)
        except ClaimCeilingViolation as exc:
            result.suppressions.append(
                Suppression(claim=claim, reason=Reason.CEILING, detail=str(exc))
            )
            return
        built = build()
        if built is None:
            return
        payload, explanation = built
        result.emissions.append(Emission(claim=claim, payload=payload, explanation=explanation))

    # ------------------------------------------------------------- main path
    def ingest(self, obs: Observation) -> EvaluationResult:
        """Apply one observation and return everything the twin may now say."""
        now = obs.at

        # 1. Which families actually arrived, and which of those may be read.
        arrived = self._arrived(obs)
        readable, consent_blocked = self._readable(arrived)

        # 2. How long the twin has been dark. Measured BEFORE the write, because the write is
        #    what makes it fresh again. ``stale`` means "the newest data this twin held, at the
        #    moment this evaluation began, was older than the freshness window" — so an
        #    evaluation that re-establishes contact after a gap is flagged, and does not alert
        #    off a comparison it cannot yet trust.
        stale = bool(self.twin.provenance) and (
            (now - self.twin.as_of) > timedelta(hours=STALE_AFTER_HOURS)
        )

        # 3. Write what we may read. Provenance is appended by TwinState.apply. An evaluation
        #    that received nothing writes nothing, so ``as_of`` keeps meaning "when data last
        #    arrived" rather than "when we last looked".
        prov_index: Optional[int] = None
        if readable:
            self._apply(obs, readable, now)
            prov_index = len(self.twin.provenance) - 1

        # 4. Tier is derived from this evaluation's readable arrivals. Not from enrolment.
        tier_state = detect_tier(readable, attribution=obs.attribution)
        downgrade = downgrade_note(self._last_tier, tier_state)
        result = EvaluationResult(
            patient_id=self.twin.patient_id,
            evaluated_at=now,
            tier_state=tier_state,
            downgrade=downgrade,
            stale=stale,
            provenance_index=prov_index,
        )
        for family in sorted(consent_blocked):
            result.suppressions.append(
                Suppression(
                    claim=Claim.CARE_PLAN,
                    reason=Reason.CONSENT,
                    detail=f"'{family}' arrived but consent for it is withheld, so it was not "
                    f"read and does not count toward the tier.",
                )
            )

        # 5. Candidate claims, in ascending order of what they require.
        self._guarded(Claim.CARE_PLAN, tier_state, result, lambda: self._care_plan(obs, stale))
        self._guarded(Claim.DEVIATION, tier_state, result, lambda: self._deviation(result, stale))
        self._guarded(
            Claim.CONVERSION_RISK, tier_state, result, lambda: self._conversion_risk(result)
        )
        self._guarded(
            Claim.CUE_OPPORTUNITY, tier_state, result, lambda: self._cue(obs, result, now)
        )

        self._last_tier = tier_state
        return result

    # ------------------------------------------------------------- internals
    @staticmethod
    def _arrived(obs: Observation) -> set[str]:
        present: set[str] = set()
        if obs.caregiver_report:
            present.add("caregiver_report")
        if obs.phone_ambient:
            present.add("phone_ambient")
        if obs.wristband:
            present.add("wristband")
        if obs.eeg:
            present.add("eeg")
        return present

    def _readable(self, arrived: set[str]) -> tuple[set[str], set[str]]:
        """Split arrivals into those consent permits reading and those it does not."""
        readable, blocked = set(), set()
        for family in arrived:
            attr = _CONSENT_FOR_SIGNAL.get(family)
            if attr is None or getattr(self.twin.consent, attr, False):
                readable.add(family)
            else:
                blocked.add(family)
        return readable, blocked

    def _apply(self, obs: Observation, readable: set[str], now: datetime) -> None:
        self.twin.apply(
            neural=obs.eeg if "eeg" in readable else None,
            physiology=obs.wristband if "wristband" in readable else None,
            mobility=obs.phone_ambient if "phone_ambient" in readable else None,
            context=obs.caregiver_report if "caregiver_report" in readable else None,
            source=obs.source,
            device_id=obs.device_id,
            at=now,
        )
        for bucket in (obs.phone_ambient, obs.wristband, obs.eeg):
            if not bucket:
                continue
            for name, value in bucket.items():
                if value is None:
                    continue
                self._history.setdefault(name, deque(maxlen=_HISTORY)).append(float(value))

    # ---- claim builders. Each returns (payload, explanation) or None.
    def _care_plan(self, obs: Observation, stale: bool) -> Optional[tuple[dict[str, Any], str]]:
        if stale:
            return None
        return (
            {
                "burden_tracking": True,
                "baseline_established": self.twin.baseline.is_established,
                "observations": self.twin.baseline.n_observations,
            },
            "care-plan support available; "
            + (
                "baseline established"
                if self.twin.baseline.is_established
                else f"baseline not yet established "
                f"({self.twin.baseline.n_observations} observations)"
            ),
        )

    def _deviation(
        self, result: EvaluationResult, stale: bool
    ) -> Optional[tuple[dict[str, Any], str]]:
        if stale:
            result.suppressions.append(
                Suppression(Claim.DEVIATION, Reason.STALE, "no data within the freshness window")
            )
            return None
        if not self.twin.baseline.is_established:
            result.suppressions.append(
                Suppression(
                    Claim.DEVIATION,
                    Reason.BASELINE,
                    f"{self.twin.baseline.n_observations} observations; no alert may fire "
                    f"before the baseline is established",
                )
            )
            return None

        for feature in self.deviation_features:
            history = self._history.get(feature)
            if not history:
                continue
            outcome = self.deviation_detector.evaluate(feature, list(history), self.twin.baseline)
            if outcome.deviated:
                return (outcome.to_dict(), f"{feature}: {outcome.detail}")

        result.suppressions.append(
            Suppression(Claim.DEVIATION, Reason.NO_DEVIATION, "within this person's own range")
        )
        return None

    def _conversion_risk(self, result: EvaluationResult) -> Optional[tuple[dict[str, Any], str]]:
        if self.risk_model is None or not getattr(self.risk_model, "_fitted", False):
            result.suppressions.append(
                Suppression(
                    Claim.CONVERSION_RISK,
                    Reason.NO_MODEL,
                    "no fitted risk model supplied to this engine",
                )
            )
            return None
        features = {**self.twin.physiology, **self.twin.mobility}
        output = self.risk_model.score(features)  # type: ignore[attr-defined]
        return (output.to_dict(), f"risk {output.score:.2f} ({output.band})")

    def _cue(
        self, obs: Observation, result: EvaluationResult, now: datetime
    ) -> Optional[tuple[dict[str, Any], str]]:
        if not self.twin.consent.permits_cue(now):
            result.suppressions.append(
                Suppression(Claim.CUE_OPPORTUNITY, Reason.CONSENT, "cue delivery not consented")
            )
            return None
        if obs.eligible_content_count <= 0:
            result.suppressions.append(
                Suppression(Claim.CUE_OPPORTUNITY, Reason.NO_CONTENT, "content library empty")
            )
            return None

        day = now.date().isoformat()
        decision = self.opportunity_detector.decide(
            FusionInput(
                place_class=obs.place_class,
                place_significance=obs.place_significance,
                hour_of_day=now.hour,
                agitation_index=self.twin.physiology.get("agitation_index"),
                theta_alpha_z=self.twin.deviation("theta_alpha_ratio"),
                eligible_content_count=obs.eligible_content_count,
                signal_quality=obs.signal_quality,
                minutes_since_last_cue=None
                if self._last_cue_at is None
                else (now - self._last_cue_at).total_seconds() / 60.0,
                cues_delivered_today=self._cues_today.get(day, 0),
                consent_permits_cue=True,
            )
        )
        if not decision.deliver:
            result.suppressions.append(
                Suppression(Claim.CUE_OPPORTUNITY, Reason.DETECTOR, decision.explain())
            )
            return None

        selection = self.cue_selector.select(obs.place_class, now.hour)
        if selection is None:
            result.suppressions.append(
                Suppression(Claim.CUE_OPPORTUNITY, Reason.DETECTOR, "all arms suppressed")
            )
            return None

        self._last_cue_at = now
        self._cues_today[day] = self._cues_today.get(day, 0) + 1
        return (
            {"arm": selection.arm.value, "confidence": decision.confidence},
            selection.explain(),
        )

    # ------------------------------------------------------------------ util
    def submit_alert(
        self, driver: str, severity: str = "moderate", now: Optional[datetime] = None
    ) -> bool:
        """Route a deviation through the alert budget. Returns True if it was delivered."""
        now = now or datetime.now(timezone.utc)
        return self.alert_budget.submit(
            Alert(
                patient_id=self.twin.patient_id, driver=driver, severity=severity, created_at=now
            ),
            now=now,
        )
