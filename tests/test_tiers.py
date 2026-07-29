"""Executable safety specification for the fidelity ladder (ADR-0010, ADR-0011).

These are not unit tests in the ordinary sense. Each one encodes a claim the architecture makes
about itself, and a failure here means the architecture no longer does what the documentation
says it does.

The central property under test: **a twin cannot emit a claim above the ceiling of the tier it is
currently operating at.** If that property is ever relaxed, this file must fail loudly, because
the alternative is a clinician acting on a conversion-risk score derived from a caregiver
questionnaire.
"""

from __future__ import annotations

import pytest

from dte.tiers import (
    Claim,
    ClaimCeilingViolation,
    Tier,
    TierState,
    assert_claim_permitted,
    detect_tier,
    downgrade_note,
)

FULL = ["caregiver_report", "phone_ambient", "wristband", "eeg"]


# ---------------------------------------------------------------------------
# Tier derivation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "signals,expected",
    [
        ([], Tier.T0_REPORT),
        (["caregiver_report"], Tier.T0_REPORT),
        (["caregiver_report", "phone_ambient"], Tier.T1_AMBIENT),
        (["caregiver_report", "phone_ambient", "wristband"], Tier.T2_PHYSIOLOGICAL),
        (FULL, Tier.T3_NEURAL),
    ],
)
def test_tier_is_derived_from_available_signals(signals, expected):
    assert detect_tier(signals).tier is expected


def test_tiers_are_contiguous_not_a_la_carte():
    """A headband with no phone and no wristband is a T0 twin, not a T3 twin.

    Skipping levels would let a sparse configuration claim a fidelity that the surrounding
    context cannot justify. Neural data with no behavioural or physiological context is exactly
    the situation the MAP must not act on.
    """
    state = detect_tier(["caregiver_report", "eeg"])
    assert state.tier is Tier.T0_REPORT
    assert not state.permits(Claim.CUE_OPPORTUNITY)


def test_unknown_signals_are_recorded_not_silently_dropped():
    state = detect_tier(["caregiver_report", "phone_ambient", "smart_toaster"])
    assert state.tier is Tier.T1_AMBIENT
    assert "smart_toaster" in state.unknown
    assert "smart_toaster" in state.explain()


def test_signal_names_are_normalised():
    assert detect_tier([" Caregiver_Report ", "PHONE_AMBIENT"]).tier is Tier.T1_AMBIENT


# ---------------------------------------------------------------------------
# The claim ceiling — the property this whole module exists to guarantee
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "signals,claim",
    [
        # A T0 twin may not assert deviation, conversion risk, or a cue opportunity.
        (["caregiver_report"], Claim.DEVIATION),
        (["caregiver_report"], Claim.CONVERSION_RISK),
        (["caregiver_report"], Claim.CUE_OPPORTUNITY),
        # A T1 twin may flag deviation but not conversion risk.
        (["caregiver_report", "phone_ambient"], Claim.CONVERSION_RISK),
        (["caregiver_report", "phone_ambient"], Claim.CUE_OPPORTUNITY),
        # A T2 twin may score conversion risk but may not run the MAP.
        (["caregiver_report", "phone_ambient", "wristband"], Claim.CUE_OPPORTUNITY),
    ],
)
def test_lower_tier_cannot_emit_higher_claim(signals, claim):
    state = detect_tier(signals)
    with pytest.raises(ClaimCeilingViolation):
        assert_claim_permitted(state, claim)


@pytest.mark.parametrize("claim", list(Claim))
def test_full_configuration_permits_every_claim(claim):
    assert_claim_permitted(detect_tier(FULL), claim)


def test_violation_message_names_the_missing_signal():
    """An operator reading the exception must be able to act on it without reading source."""
    state = detect_tier(["caregiver_report", "phone_ambient"])
    with pytest.raises(ClaimCeilingViolation) as exc:
        assert_claim_permitted(state, Claim.CONVERSION_RISK)
    assert "wristband" in str(exc.value)
    assert "no bypass" in str(exc.value).lower()


def test_there_is_no_bypass_parameter():
    """Guards against the obvious future regression: someone adding force=True.

    If this test starts failing because a bypass was added, that change requires an ADR
    superseding ADR-0010 — not a fix to this test.
    """
    import inspect

    sig = inspect.signature(assert_claim_permitted)
    assert list(sig.parameters) == ["state", "claim"]


# ---------------------------------------------------------------------------
# Graceful degradation
# ---------------------------------------------------------------------------


def test_removing_the_headband_downgrades_the_twin():
    """The modal real-world event: a person takes the headband off.

    The twin must become a T2 twin and say so, rather than continuing to assert T3 claims
    against stale neural data.
    """
    before = detect_tier(FULL)
    after = detect_tier(["caregiver_report", "phone_ambient", "wristband"])

    assert before.tier is Tier.T3_NEURAL
    assert after.tier is Tier.T2_PHYSIOLOGICAL
    assert after.permits(Claim.CONVERSION_RISK)
    assert not after.permits(Claim.CUE_OPPORTUNITY)

    note = downgrade_note(before, after)
    assert note is not None
    assert "eeg" in note
    assert "memory-cue" in note


def test_no_downgrade_note_when_fidelity_is_stable_or_improving():
    t2 = detect_tier(["caregiver_report", "phone_ambient", "wristband"])
    t3 = detect_tier(FULL)
    assert downgrade_note(t2, t2) is None
    assert downgrade_note(t2, t3) is None
    assert downgrade_note(None, t3) is None


def test_missing_for_next_explains_the_gap():
    state = detect_tier(["caregiver_report"])
    assert state.missing_for_next == frozenset({"phone_ambient"})
    assert "phone_ambient" in state.explain()


def test_top_tier_has_nothing_further_to_reach():
    assert detect_tier(FULL).missing_for_next == frozenset()


# ---------------------------------------------------------------------------
# Serialisation — the tier travels with any output that depends on it
# ---------------------------------------------------------------------------


def test_tier_state_serialises_with_its_permitted_claims():
    d = detect_tier(["caregiver_report", "phone_ambient", "wristband"]).to_dict()
    assert d["tier"] == int(Tier.T2_PHYSIOLOGICAL)
    assert "CONVERSION_RISK" in d["permitted_claims"]
    assert "CUE_OPPORTUNITY" not in d["permitted_claims"]
    assert d["missing_for_next_tier"] == ["eeg"]


def test_tier_state_is_immutable():
    """Tier is derived, never assigned. An immutable record makes that structural."""
    state = detect_tier(FULL)
    with pytest.raises(Exception):
        state.tier = Tier.T0_REPORT  # type: ignore[misc]


def test_every_claim_has_a_declared_minimum_tier():
    """Adding a Claim without declaring its ceiling must not silently default to permissive."""
    from dte.tiers import MINIMUM_TIER_FOR_CLAIM

    assert set(MINIMUM_TIER_FOR_CLAIM) == set(Claim)
