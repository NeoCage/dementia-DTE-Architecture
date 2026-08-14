"""Fidelity tiers and claim ceilings — the deployable-configuration constraint.

Implements ``docs/adr/0010-tiered-fidelity-ladder.md`` and
``docs/adr/0011-non-neural-core.md``.

WHY THIS MODULE EXISTS
----------------------
The original architecture assumed EEG. Every component was designed around a neural signal
being present, and the honest admission that the theta-to-receptivity inference was the weakest
link in the system sat in §7.6 without changing anything upstream of it.

Two pieces of evidence forced the change, and neither concerns adherence:

* Resting-state EEG classifiers separate established Alzheimer's disease from controls at around
  AUC 0.85, and mild cognitive impairment at around **AUC 0.60** — close to chance, and MCI is
  precisely the population this system targets (Meghdadi et al., 2021).
* A plasma p-tau217 blood test reached **91%** diagnostic accuracy in primary and secondary care,
  against **61%** for primary care physicians and **73%** for dementia specialists using clinical
  examination, cognitive testing and CT (Palmqvist et al., 2024).

A design that *requires* neural sensing therefore places its weight on its least-evidenced
component, while a cheap blood test outperforms the specialists it is meant to assist. The
response is not to abandon EEG. It is to demote it to an optional high-fidelity tier that has to
earn its cost, and to make the base configuration run on hardware people already own.

THE INVARIANT THIS MODULE ENFORCES
----------------------------------
**A twin may not emit a claim above the ceiling of the tier it is currently operating at.**

"Currently" is load-bearing. Tier is *derived from live signal availability on every evaluation*,
never configured once at enrolment. A patient enrolled with an EEG headband who takes it off is a
Tier 2 patient until it goes back on, and the twin says so rather than continuing to assert
Tier 3 claims against stale neural data.

This is the same enforcement pattern as ``RiskOutput.__post_init__`` (ADR-0006): the unsafe state
is made unrepresentable rather than discouraged. There is no bypass flag, because a bypass flag
is what gets set at three in the morning during a demo and never unset.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import Optional


class Tier(IntEnum):
    """Sensing fidelity available to the twin right now.

    Ordered and comparable: ``Tier.T2 >= Tier.T1`` is meaningful and is used for ceiling checks.
    """

    T0_REPORT = 0
    T1_AMBIENT = 1
    T2_PHYSIOLOGICAL = 2
    T3_NEURAL = 3

    @property
    def label(self) -> str:
        return {
            Tier.T0_REPORT: "T0 — caregiver and clinician report only",
            Tier.T1_AMBIENT: "T1 — ambient smartphone sensing",
            Tier.T2_PHYSIOLOGICAL: "T2 — wristband physiology",
            Tier.T3_NEURAL: "T3 — neural sensing",
        }[self]


class Claim(IntEnum):
    """What the twin is asserting. Ordered by the sensing fidelity each one requires."""

    CARE_PLAN = 0
    DEVIATION = 1
    DEVIATION_ATTRIBUTION = 4
    CONVERSION_RISK = 2
    CUE_OPPORTUNITY = 3

    @property
    def label(self) -> str:
        return {
            Claim.CARE_PLAN: "care-plan support and burden tracking",
            Claim.DEVIATION: "deviation from this person's own baseline",
            Claim.DEVIATION_ATTRIBUTION: (
                "whether this deviation is more likely neurodegenerative or reversible"
            ),
            Claim.CONVERSION_RISK: "MCI-to-dementia conversion risk",
            Claim.CUE_OPPORTUNITY: "real-time memory-cue opportunity",
        }[self]


class AttributionBasis(IntEnum):
    """What the twin knows about the *cause* of an observed deviation (ADR-0013).

    Orthogonal to :class:`Tier`, deliberately. Tier governs what can be observed; attribution
    basis governs what may be said about why. A T1 household with a confirmed biomarker and a T3
    household with none are different in kind, not in degree, and neither dominates the other.

    Ordered only for convenience of comparison. A3_EXCLUDED is NOT "better" than A2_CONFIRMED --
    both are informative, and the negative result is frequently the more actionable of the two
    because it redirects a clinician toward a reversible cause.
    """

    A0_NONE = 0
    A1_CLINICAL = 1
    A2_CONFIRMED = 2
    A3_EXCLUDED = 3

    @property
    def label(self) -> str:
        return {
            AttributionBasis.A0_NONE: "A0 - no biomarker information",
            AttributionBasis.A1_CLINICAL: "A1 - clinical diagnosis, unconfirmed",
            AttributionBasis.A2_CONFIRMED: "A2 - biomarker positive",
            AttributionBasis.A3_EXCLUDED: "A3 - biomarker negative",
        }[self]

    @property
    def supports_attribution(self) -> bool:
        """Whether this basis licenses any statement about cause.

        Only a present result does. A clinical diagnosis without biomarker confirmation is not a
        basis for attributing a *specific* deviation to pathology, which is the whole point of
        separating A1 from A2.
        """
        return self in (AttributionBasis.A2_CONFIRMED, AttributionBasis.A3_EXCLUDED)


# Claims that additionally require an attribution basis (ADR-0013). Absence of a basis lowers the
# ceiling; it never blocks enrolment or withholds a lower claim.
_REQUIRES_ATTRIBUTION: frozenset[str] = frozenset({"DEVIATION_ATTRIBUTION"})


# The ceiling table. A tier permits every claim whose required tier is at or below it.
#
# CUE_OPPORTUNITY is T3-only and that is the whole point of the Memory Anchoring Pipeline being
# an optional tier rather than the spine: if the neural channel is absent, the MAP does not
# degrade to a worse cue — it goes silent. Silence is the designed failure mode (P5).
MINIMUM_TIER_FOR_CLAIM: dict[Claim, Tier] = {
    Claim.CARE_PLAN: Tier.T0_REPORT,
    Claim.DEVIATION: Tier.T1_AMBIENT,
    Claim.DEVIATION_ATTRIBUTION: Tier.T1_AMBIENT,
    Claim.CONVERSION_RISK: Tier.T2_PHYSIOLOGICAL,
    Claim.CUE_OPPORTUNITY: Tier.T3_NEURAL,
}

# Signal families, and the tier each one unlocks. Tier is the highest contiguous level for which
# all prerequisite families are present — a wristband without a phone to relay it does not make a
# T2 twin, it makes a T0 twin with an unreachable sensor.
_TIER_REQUIREMENTS: dict[Tier, frozenset[str]] = {
    Tier.T0_REPORT: frozenset({"caregiver_report"}),
    Tier.T1_AMBIENT: frozenset({"caregiver_report", "phone_ambient"}),
    Tier.T2_PHYSIOLOGICAL: frozenset({"caregiver_report", "phone_ambient", "wristband"}),
    Tier.T3_NEURAL: frozenset({"caregiver_report", "phone_ambient", "wristband", "eeg"}),
}

KNOWN_SIGNALS: frozenset[str] = frozenset(
    {"caregiver_report", "phone_ambient", "wristband", "eeg"}
)


class ClaimCeilingViolation(RuntimeError):
    """Raised when a component attempts a claim above its current tier's ceiling.

    Deliberately a hard failure rather than a logged warning. A silently downgraded claim is
    worse than a crash: the clinician sees a number and has no way to know the sensing that was
    supposed to justify it was absent.
    """


@dataclass(frozen=True)
class TierState:
    """The tier a twin is operating at, with the provenance to explain it.

    ``missing_for_next`` is included because the most common operational question is not "what
    tier am I?" but "why am I not one tier higher?", and a nurse-navigator should be able to
    answer that without reading code.
    """

    tier: Tier
    attribution: AttributionBasis = AttributionBasis.A0_NONE
    available: frozenset[str] = field(default_factory=frozenset)
    unknown: frozenset[str] = field(default_factory=frozenset)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def missing_for_next(self) -> frozenset[str]:
        nxt = Tier(self.tier + 1) if self.tier < Tier.T3_NEURAL else None
        if nxt is None:
            return frozenset()
        return _TIER_REQUIREMENTS[nxt] - self.available

    @property
    def viable(self) -> bool:
        """Whether the twin has the minimum input to make any claim at all.

        T0 is the floor of the ladder, but a record with *nothing* reporting — not even a
        caregiver entry — sits below the floor. Such a twin is not a low-fidelity twin; it is an
        empty record, and an empty record must not assert even care-plan support.

        This distinction was found by scenario S09 in ``tests/fixtures/tier_scenarios.json``
        rather than by inspection, which is the argument for keeping the scenarios in a file a
        clinician can read.
        """
        return _TIER_REQUIREMENTS[Tier.T0_REPORT] <= self.available

    def permits(self, claim: Claim) -> bool:
        """Evaluate both axes. Either one can refuse (ADR-0010, ADR-0013)."""
        if not self.viable:
            return False
        if self.tier < MINIMUM_TIER_FOR_CLAIM[claim]:
            return False
        if claim.name in _REQUIRES_ATTRIBUTION and not self.attribution.supports_attribution:
            return False
        return True

    def permitted_claims(self) -> list[Claim]:
        return [c for c in Claim if self.permits(c)]

    def explain(self) -> str:
        """One line a human can act on."""
        if not self.viable:
            return (
                "No signals reporting. This record cannot support any claim, including "
                "care-plan support, until a caregiver report is entered."
            )
        base = f"Operating at {self.tier.label}; {self.attribution.label}."
        if self.missing_for_next:
            nxt = Tier(self.tier + 1)
            base += (
                f" To reach {nxt.label}, the following signal(s) must become available: "
                + ", ".join(sorted(self.missing_for_next))
                + "."
            )
        if self.unknown:
            base += (
                " Ignored unrecognised signal(s): " + ", ".join(sorted(self.unknown)) + "."
            )
        return base

    def to_dict(self) -> dict[str, object]:
        return {
            "tier": int(self.tier),
            "tier_label": self.tier.label,
            "attribution": int(self.attribution),
            "attribution_label": self.attribution.label,
            "available_signals": sorted(self.available),
            "missing_for_next_tier": sorted(self.missing_for_next),
            "permitted_claims": [c.name for c in self.permitted_claims()],
            "evaluated_at": self.evaluated_at.isoformat(),
        }


def detect_tier(
    available_signals: Iterable[str],
    attribution: AttributionBasis = AttributionBasis.A0_NONE,
) -> TierState:
    """Derive the current tier from the signals actually available on this evaluation.

    Unknown signal names are recorded rather than silently dropped: a typo in a device
    integration should surface as an unexplained tier, not as a mysteriously absent alert.

    Note the contiguity rule. Signals are cumulative, so a twin with ``{"caregiver_report",
    "eeg"}`` — a headband but no phone to relay it and no wristband — is T0, not T3. Skipping
    levels would let a sparse configuration claim a fidelity its supporting context cannot
    justify.
    """
    provided = {s.strip().lower() for s in available_signals if s and s.strip()}
    unknown = frozenset(provided - KNOWN_SIGNALS)
    known = frozenset(provided & KNOWN_SIGNALS)

    tier = Tier.T0_REPORT
    if not _TIER_REQUIREMENTS[Tier.T0_REPORT] <= known:
        # Without even a caregiver report there is no twin. T0 is the floor, and a twin at the
        # floor with nothing under it still may not make claims — CARE_PLAN requires the report.
        return TierState(
            tier=Tier.T0_REPORT, attribution=attribution, available=known, unknown=unknown
        )

    for candidate in (Tier.T1_AMBIENT, Tier.T2_PHYSIOLOGICAL, Tier.T3_NEURAL):
        if _TIER_REQUIREMENTS[candidate] <= known:
            tier = candidate
        else:
            break

    return TierState(tier=tier, attribution=attribution, available=known, unknown=unknown)


def assert_claim_permitted(state: TierState, claim: Claim) -> None:
    """Enforce the ceiling. Raises ``ClaimCeilingViolation`` rather than degrading quietly."""
    if state.permits(claim):
        return
    if not state.viable:
        raise ClaimCeilingViolation(
            f"claim ceiling violated: '{claim.label}' attempted on a record with no reporting "
            "signals. Even care-plan support requires a caregiver report (ADR-0010)."
        )
    if (
        claim.name in _REQUIRES_ATTRIBUTION
        and state.tier >= MINIMUM_TIER_FOR_CLAIM[claim]
        and not state.attribution.supports_attribution
    ):
        raise ClaimCeilingViolation(
            f"claim ceiling violated: '{claim.label}' requires a biomarker result to be present "
            f"(A2_CONFIRMED or A3_EXCLUDED), but the twin has {state.attribution.label}. "
            "Sensing tier is sufficient; the attribution axis is not. A biomarker is never "
            "required for enrolment or for lower claims (ADR-0013)."
        )
    required = MINIMUM_TIER_FOR_CLAIM[claim]
    raise ClaimCeilingViolation(
        f"claim ceiling violated: '{claim.label}' requires {required.label}, "
        f"but the twin is operating at {state.tier.label}. "
        f"Missing signal(s) for the next tier: "
        f"{', '.join(sorted(state.missing_for_next)) or 'none'}. "
        "There is no bypass path (ADR-0010)."
    )


def downgrade_note(previous: Optional[TierState], current: TierState) -> Optional[str]:
    """Human-readable note when a twin loses fidelity between evaluations.

    Surfaced to the nurse-navigator rather than the patient. A person who has taken off a
    headband has usually done so for a reason, and the system's job is to keep working at the
    fidelity that remains, not to nag them back into compliance.
    """
    if previous is None or current.tier >= previous.tier:
        return None
    lost = sorted(previous.available - current.available)
    return (
        f"Fidelity reduced from {previous.tier.label} to {current.tier.label}. "
        f"Signal(s) no longer available: {', '.join(lost) or 'unspecified'}. "
        f"Claims now suspended: "
        f"{', '.join(c.label for c in previous.permitted_claims() if not current.permits(c))}."
    )
