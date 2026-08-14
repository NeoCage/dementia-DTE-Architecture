"""Multimodal opportunity detector and the Alert Budget Governor.

Implements ``docs/03-digital-twin-engine.md`` §3.3 and §3.7, and
``docs/04-memory-anchoring-pipeline.md``.

THE CENTRAL DESIGN ASYMMETRY
----------------------------
Four channels feed the fusion: context, physiology, neural and content. Three of them contribute
to a weighted confidence score. **Physiology does not.** It acts as a hard VETO.

A cue delivered to an agitated person is not merely ineffective — it is likely to be actively
distressing and to teach the person to resent the device. The architecture treats "make it worse"
as a categorically different error from "miss an opportunity". Elevated agitation therefore blocks
a cue outright rather than nudging a score downward where a strong neural signal could outvote it.

SILENCE IS A FIRST-CLASS OUTCOME
--------------------------------
``OpportunityDecision`` is returned whether or not a cue is delivered, and it records WHY. Silence
is a logged decision, not an absence of behaviour. That is what makes threshold calibration
possible and what lets a clinician answer a family's question: "why didn't it do anything
on Tuesday?"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from dte.config import (
    AGITATION_VETO,
    DAILY_CUE_BUDGET,
    FUSION_WEIGHTS,
    OPPORTUNITY_THRESHOLD,
    QUIET_HOURS,
    REFRACTORY_MINUTES,
    AlertBudgetConfig,
)
from dte.tiers import Claim, TierState

# Signal quality at or above this level is treated as "good enough" and does not attenuate
# confidence. Below it, confidence is progressively eroded. Distinct from the hard quality gate
# (MIN_USABLE_EPOCH_FRACTION = 0.60), which decides whether to infer at all.
GOOD_QUALITY = 0.85

PLACE_SIGNIFICANCE = {
    "known-significant": 0.90,
    "home": 0.40,
    "known-routine": 0.30,
    # Novel places score LOW, not high. Novelty is disorienting, and this system is not a
    # tour guide (docs/04 §4.4).
    "novel": 0.10,
    "unknown": 0.05,
}


@dataclass
class FusionInput:
    """Everything the detector needs for one decision."""

    # Context channel
    place_class: str = "unknown"
    place_significance: Optional[float] = None
    hour_of_day: int = 12
    minutes_since_last_cue: Optional[float] = None
    cues_delivered_today: int = 0

    # Physiology channel (VETO)
    agitation_index: Optional[float] = None

    # Neural channel
    theta_alpha_ratio: Optional[float] = None
    theta_alpha_z: Optional[float] = None  # deviation vs this patient's own baseline

    # Content channel
    eligible_content_count: int = 0

    # Quality
    signal_quality: float = 0.0

    # Consent
    consent_permits_cue: bool = False


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class OpportunityDecision:
    """The outcome of one detection cycle — delivered or not."""

    deliver: bool
    confidence: float
    threshold: float
    channel_scores: dict[str, float] = field(default_factory=dict)
    gates: list[GateResult] = field(default_factory=list)
    reason: str = ""
    tier: Optional[int] = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def failed_gates(self) -> list[str]:
        return [g.name for g in self.gates if not g.passed]

    def explain(self) -> str:
        """One-line human-readable trace, in the style of docs/04 §4.7."""
        parts = [f"{k}={v:.2f}" for k, v in self.channel_scores.items()]
        gate_str = "all-pass" if not self.failed_gates else "FAILED:" + ",".join(self.failed_gates)
        verdict = "DELIVER" if self.deliver else "SILENT"
        return (
            f"{' '.join(parts)} conf={self.confidence:.2f} tau={self.threshold:.2f} "
            f"gates[{gate_str}] -> {verdict} ({self.reason})"
        )


class OpportunityDetector:
    """Decides whether *now* is a memory-retrieval opportunity.

    Precision-weighted by design: it is built to miss opportunities rather than to fire wrongly.
    A missed cue costs one moment; a wrong cue costs trust, and trust does not come back
    (docs/04 §4.2).
    """

    def __init__(
        self,
        threshold: float = OPPORTUNITY_THRESHOLD,
        weights: Optional[dict[str, float]] = None,
        agitation_veto: float = AGITATION_VETO,
        daily_budget: int = DAILY_CUE_BUDGET,
        refractory_minutes: int = REFRACTORY_MINUTES,
        quiet_hours: tuple[int, int] = QUIET_HOURS,
    ) -> None:
        self.threshold = threshold
        self.weights = dict(weights or FUSION_WEIGHTS)
        self.agitation_veto = agitation_veto
        self.daily_budget = daily_budget
        self.refractory_minutes = refractory_minutes
        self.quiet_hours = quiet_hours

    # ------------------------------------------------------------------ channels
    def _context_score(self, inp: FusionInput) -> float:
        base = (
            inp.place_significance
            if inp.place_significance is not None
            else PLACE_SIGNIFICANCE.get(inp.place_class, 0.05)
        )
        # Mild circadian shaping: late-afternoon confusion is common, so a cue delivered then is
        # less likely to land well. Deliberately gentle — this is a weak prior, not evidence.
        if 15 <= inp.hour_of_day <= 18:
            base *= 0.90
        return float(min(max(base, 0.0), 1.0))

    def _neural_score(self, inp: FusionInput) -> float:
        """Score theta elevation relative to the patient's OWN baseline.

        HONEST CAVEAT (docs/07 §7.6): the inference from "theta is elevated relative to baseline"
        to "this person is receptive to a cue right now" is the least well-evidenced link in this
        entire system. It is literature-supported at the group level and NOT established at the
        single-trial, single-person level. The neural-channel ablation described in docs/07 §7.6
        is the single most valuable experiment anyone could run against this architecture.
        """
        if inp.theta_alpha_z is not None:
            # Map z in [0, 3] onto [0, 1]; below-baseline theta scores 0.
            return float(min(max(inp.theta_alpha_z / 3.0, 0.0), 1.0))
        if inp.theta_alpha_ratio is not None:
            return float(min(max((inp.theta_alpha_ratio - 1.0) / 1.5, 0.0), 1.0))
        return 0.0

    def _content_score(self, inp: FusionInput) -> float:
        """Content availability. There is NO generic fallback content.

        A stock photograph of a beach does not cue an episodic memory; it just interrupts a walk
        (docs/04 §4.4).
        """
        if inp.eligible_content_count <= 0:
            return 0.0
        return float(min(1.0, 0.5 + 0.25 * min(inp.eligible_content_count, 2)))

    # ------------------------------------------------------------------ gates
    def _gates(self, inp: FusionInput) -> list[GateResult]:
        g: list[GateResult] = []

        # 1. Agitation veto — the asymmetry that defines this module.
        agit = inp.agitation_index
        if agit is None:
            g.append(GateResult("agitation", False, "agitation unknown; fail closed"))
        else:
            g.append(
                GateResult(
                    "agitation",
                    agit <= self.agitation_veto,
                    f"{agit:.2f} vs veto {self.agitation_veto:.2f}",
                )
            )

        # 2. Refractory period — prevents nagging.
        mins = inp.minutes_since_last_cue
        g.append(
            GateResult(
                "refractory",
                mins is None or mins >= self.refractory_minutes,
                f"{mins if mins is not None else 'never'} min since last cue "
                f"(min {self.refractory_minutes})",
            )
        )

        # 3. Quiet hours — sleep is protected.
        start, end = self.quiet_hours
        in_quiet = inp.hour_of_day >= start or inp.hour_of_day < end
        g.append(GateResult("quiet_hours", not in_quiet, f"hour {inp.hour_of_day}"))

        # 4. Consent, including the patient stop-command.
        g.append(GateResult("consent", inp.consent_permits_cue, "cue consent active"))

        # 5. Signal quality — never infer from junk.
        g.append(
            GateResult("quality", inp.signal_quality >= 0.60, f"quality {inp.signal_quality:.2f}")
        )

        # 6. Daily burden ceiling.
        g.append(
            GateResult(
                "daily_budget",
                inp.cues_delivered_today < self.daily_budget,
                f"{inp.cues_delivered_today}/{self.daily_budget} used today",
            )
        )
        return g

    # ------------------------------------------------------------------ decide
    def decide(
        self,
        inp: FusionInput,
        tier_state: Optional[TierState] = None,
    ) -> OpportunityDecision:
        """Decide whether to deliver a cue.

        TIER CEILING (ADR-0010). The Memory Anchoring Pipeline is a Tier 3 capability. When the
        twin is operating below T3 — most commonly because the headband is off — this returns
        SILENT rather than raising.

        That asymmetry with ``RiskModel.predict`` is deliberate. A risk score emitted without the
        sensing to justify it is a clinician acting on a fiction, so that path raises. A cue not
        delivered is simply a quiet afternoon, which is the designed failure mode of this whole
        pipeline (P5). Degrading to silence IS the correct behaviour here; degrading to a
        lower-quality cue would not be.
        """
        if tier_state is not None and not tier_state.permits(Claim.CUE_OPPORTUNITY):
            return OpportunityDecision(
                deliver=False,
                confidence=0.0,
                threshold=self.threshold,
                channel_scores={},
                gates=[],
                reason=(
                    "tier ceiling: memory cueing requires neural sensing; twin is at "
                    f"{tier_state.tier.label}"
                ),
                tier=int(tier_state.tier),
            )

        scores = {
            "context": self._context_score(inp),
            "neural": self._neural_score(inp),
            "content": self._content_score(inp),
        }
        raw = sum(self.weights.get(k, 0.0) * v for k, v in scores.items())
        # Poor signal quality attenuates confidence rather than being ignored.
        #
        # Attenuation is relative to a "good enough" reference (GOOD_QUALITY), not to a perfect
        # 1.0. Using raw quality directly would double-penalise: quality is ALREADY subject to a
        # hard gate at 0.60, so multiplying by it again means a recording of acceptable quality
        # silently raises the effective threshold (0.62 / 0.82 = 0.76 on the raw score). That made
        # the pipeline unable to fire under any realistic combination of channel scores — a
        # miscalibration, not caution.
        attenuation = float(min(max(inp.signal_quality / GOOD_QUALITY, 0.0), 1.0))
        confidence = raw * attenuation

        gates = self._gates(inp)
        failed = [g for g in gates if not g.passed]

        if failed:
            return OpportunityDecision(
                deliver=False,
                confidence=confidence,
                threshold=self.threshold,
                channel_scores=scores,
                gates=gates,
                reason=f"hard gate failed: {failed[0].name} ({failed[0].detail})",
                tier=int(tier_state.tier) if tier_state else None,
            )

        if confidence < self.threshold:
            return OpportunityDecision(
                deliver=False,
                confidence=confidence,
                threshold=self.threshold,
                channel_scores=scores,
                gates=gates,
                reason="below confidence threshold",
                tier=int(tier_state.tier) if tier_state else None,
            )

        return OpportunityDecision(
            deliver=True,
            confidence=confidence,
            threshold=self.threshold,
            channel_scores=scores,
            gates=gates,
            reason="all gates passed and confidence above threshold",
            tier=int(tier_state.tier) if tier_state else None,
        )


# ======================================================================================
# Alert Budget Governor
# ======================================================================================


@dataclass
class Alert:
    patient_id: str
    driver: str
    severity: str = "moderate"
    novelty: float = 1.0
    confidence: float = 1.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def rank(self) -> float:
        sev = {"low": 1.0, "moderate": 2.0, "high": 3.0}.get(self.severity, 2.0)
        return sev * self.novelty * self.confidence


class AlertBudget:
    """Caps alert volume against a ceiling the receiving team agreed BEFORE launch.

    Implements ``docs/03-digital-twin-engine.md`` §3.7.

    WHY THIS EXISTS AS A COMPONENT RATHER THAN A POLICY
    ---------------------------------------------------
    A monitoring pilot was abandoned after six weeks — not because the model was wrong, but
    because nobody had checked whether the alert volume was survivable for the humans receiving
    it (docs/02 §2.4). Alert volume is therefore treated as a hard design constraint with a
    pre-agreed ceiling, not as an emergent property to be tuned after go-live.

    Suppressed alerts are LOGGED, so throttling is auditable. You must be able to answer
    "did we hide something that mattered?"
    """

    def __init__(self, config: Optional[AlertBudgetConfig] = None) -> None:
        self.config = config or AlertBudgetConfig()
        self._delivered: list[Alert] = []
        self.suppressed: list[Alert] = []

    def _window_start(self, now: datetime) -> datetime:
        return now - timedelta(days=7)

    def delivered_this_week(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        cutoff = self._window_start(now)
        self._delivered = [a for a in self._delivered if a.created_at >= cutoff]
        return len(self._delivered)

    def submit(self, alert: Alert, now: Optional[datetime] = None) -> bool:
        """Submit a candidate alert. Returns True if delivered, False if deferred."""
        now = now or datetime.now(timezone.utc)

        # Deduplicate: same patient, same driver, already live this week.
        cutoff = self._window_start(now)
        for existing in self._delivered:
            if (
                existing.patient_id == alert.patient_id
                and existing.driver == alert.driver
                and existing.created_at >= cutoff
            ):
                self.suppressed.append(alert)
                return False

        if self.delivered_this_week(now) >= self.config.weekly_ceiling:
            self.suppressed.append(alert)
            return False

        self._delivered.append(alert)
        return True

    def suppression_report(self) -> dict[str, object]:
        """Feeds the weekly review: was anything important suppressed?

        If the answer is repeatedly yes, the ceiling is renegotiated WITH the team — it is never
        silently raised.
        """
        return {
            "weekly_ceiling": self.config.weekly_ceiling,
            "agreed_with": self.config.agreed_with,
            "agreed_on": self.config.agreed_on,
            "delivered": len(self._delivered),
            "suppressed": len(self.suppressed),
            "suppressed_drivers": sorted({a.driver for a in self.suppressed}),
            "action_required": len(self.suppressed) > 0,
            "note": (
                "Review whether any suppressed alert was clinically significant. If so, "
                "renegotiate the ceiling with the receiving team. Do not raise it silently."
            ),
        }
