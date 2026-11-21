"""End-to-end tests for the evaluation path.

Every other test file in this suite verifies one mechanism. This one verifies that the
mechanisms compose, which is a different claim and the one the architecture actually makes:
a twin may not emit a claim above the ceiling of the tier it is operating at *right now*.

The central test is :func:`test_no_emission_ever_exceeds_the_active_tier`. It walks a
household through ninety days of changing sensing — gaining a phone, gaining a wristband,
losing the wristband, going dark, coming back — and asserts the invariant on every single
evaluation rather than at chosen moments. If the ceiling check is removed from
``TwinEngine._guarded``, that test fails, and so do most of the others here. That is the
point of the file: the safety property is falsifiable by deletion, in about five minutes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dte.engine import Observation, Reason, TwinEngine
from dte.tiers import MINIMUM_TIER_FOR_CLAIM, AttributionBasis, Claim, Tier
from dte.twin import ConsentSnapshot, TwinState

DAY = timedelta(days=1)


def _consent(**kwargs: bool) -> ConsentSnapshot:
    base = dict(
        location_data=True,
        wearable_physiology=True,
        neural_data=True,
        cue_delivery=True,
    )
    base.update(kwargs)
    return ConsentSnapshot(**base)  # type: ignore[arg-type]


def _engine(**consent_kwargs: bool) -> TwinEngine:
    twin = TwinState(patient_id="household-001", consent=_consent(**consent_kwargs))
    return TwinEngine(twin)


def _obs(
    at: datetime,
    *,
    phone: bool = False,
    band: bool = False,
    eeg: bool = False,
    gait: float = 1.10,
    report: bool = True,
    content: int = 3,
) -> Observation:
    return Observation(
        patient_id="household-001",
        at=at,
        caregiver_report={"mood": "settled"} if report else None,
        phone_ambient={"gait_speed": gait} if phone else None,
        wristband={"hrv_rmssd": 34.0, "agitation_index": 0.2} if band else None,
        eeg={"theta_alpha_ratio": 1.4} if eeg else None,
        place_class="kitchen",
        place_significance=0.8,
        eligible_content_count=content,
        signal_quality=0.9,
    )


# --------------------------------------------------------------- the invariant
def test_no_emission_ever_exceeds_the_active_tier() -> None:
    """The whole architecture in one assertion, checked on every evaluation.

    Delete the ``assert_claim_permitted`` call in ``TwinEngine._guarded`` and this fails.
    """
    engine = _engine()
    start = datetime.now(timezone.utc) - 90 * DAY
    checked = 0
    tiers_seen: set[Tier] = set()
    claims_seen: set[Claim] = set()

    for day in range(90):
        at = start + day * DAY
        phone = 10 <= day < 80  # phone arrives day 10, is lost day 80
        band = 30 <= day < 55  # wristband arrives day 30, is lost day 55
        eeg = 40 <= day < 55  # headband only while the band is also worn
        if 70 <= day < 74:
            continue  # four days dark

        # Gait holds steady, then declines from day 60 so that a real deviation fires and the
        # invariant is tested against a higher claim, not only against care-plan support.
        # The decline continues past day 80, when the phone is lost: the engine still holds
        # the gait history, so an unguarded build would happily emit a DEVIATION claim while
        # the twin has fallen back to T0. That is precisely the failure the ceiling prevents,
        # and it is why this walk ends with the phone absent rather than present.
        gait = 1.10 if day < 60 else 1.10 - 0.035 * (day - 59)

        result = engine.ingest(_obs(at, phone=phone, band=band, eeg=eeg, gait=gait))
        tiers_seen.add(result.tier_state.tier)

        for emission in result.emissions:
            required = MINIMUM_TIER_FOR_CLAIM[emission.claim]
            assert result.tier_state.tier >= required, (
                f"day {day}: emitted {emission.claim.name} at "
                f"{result.tier_state.tier.name}, which is below the required {required.name}"
            )
            assert result.tier_state.permits(emission.claim)
            claims_seen.add(emission.claim)
            checked += 1

    assert checked >= 80, "the walk should have produced plenty of emissions to check"
    assert len(tiers_seen) >= 3, f"the walk should exercise the ladder, saw only {tiers_seen}"
    assert Claim.DEVIATION in claims_seen, (
        "the walk never emitted a claim above the floor, so the invariant was only tested "
        "against care-plan support"
    )


# ------------------------------------------------------------- tier behaviour
def test_tier_climbs_as_sensing_arrives() -> None:
    engine = _engine()
    at = datetime.now(timezone.utc) - 30 * DAY

    assert engine.ingest(_obs(at)).tier_state.tier is Tier.T0_REPORT
    assert engine.ingest(_obs(at + DAY, phone=True)).tier_state.tier is Tier.T1_AMBIENT
    assert (
        engine.ingest(_obs(at + 2 * DAY, phone=True, band=True)).tier_state.tier
        is Tier.T2_PHYSIOLOGICAL
    )
    assert (
        engine.ingest(_obs(at + 3 * DAY, phone=True, band=True, eeg=True)).tier_state.tier
        is Tier.T3_NEURAL
    )


def test_tier_falls_back_on_the_very_next_evaluation_when_sensing_stops() -> None:
    """Tier is derived per evaluation, not held from enrolment."""
    engine = _engine()
    at = datetime.now(timezone.utc) - 30 * DAY

    high = engine.ingest(_obs(at, phone=True, band=True, eeg=True))
    assert high.tier_state.tier is Tier.T3_NEURAL

    dropped = engine.ingest(_obs(at + DAY, phone=True, band=True))  # headband taken off
    assert dropped.tier_state.tier is Tier.T2_PHYSIOLOGICAL
    assert dropped.downgrade is not None, "a fidelity drop must be announced"
    assert dropped.suppression_for(Claim.CUE_OPPORTUNITY).reason == Reason.CEILING


def test_a_record_with_no_reporting_signal_may_not_even_support_a_care_plan() -> None:
    engine = _engine()
    at = datetime.now(timezone.utc) - 30 * DAY
    result = engine.ingest(_obs(at, report=False))

    assert not result.tier_state.viable
    assert result.silent
    assert result.suppression_for(Claim.CARE_PLAN).reason == Reason.CEILING


def test_a_wristband_without_a_phone_does_not_make_a_t2_twin() -> None:
    """Contiguity: skipping a level is not permitted, however good the sensor."""
    engine = _engine()
    at = datetime.now(timezone.utc) - 30 * DAY
    result = engine.ingest(_obs(at, band=True, eeg=True))

    assert result.tier_state.tier is Tier.T0_REPORT
    assert not result.tier_state.permits(Claim.CONVERSION_RISK)


# ------------------------------------------------------------------- consent
def test_withdrawing_consent_lowers_the_tier_rather_than_hiding_the_output() -> None:
    """Consent gates the read, so an unconsented modality cannot support a tier.

    This is the property that distinguishes a consent check bolted onto an output from
    consent as an architectural constraint.
    """
    engine = _engine(neural_data=False)
    at = datetime.now(timezone.utc) - 30 * DAY

    result = engine.ingest(_obs(at, phone=True, band=True, eeg=True))

    assert result.tier_state.tier is Tier.T2_PHYSIOLOGICAL, "EEG arrived but may not be read"
    assert "eeg" not in result.tier_state.available
    assert not engine.twin.neural, "unreadable data must not be written to the twin"
    assert any(s.reason == Reason.CONSENT for s in result.suppressions)


def test_a_patient_stop_overrides_an_active_cue_consent() -> None:
    engine = _engine()
    at = datetime.now(timezone.utc) - 30 * DAY
    engine.twin.consent.patient_stop_until = at + 7 * DAY

    result = engine.ingest(_obs(at, phone=True, band=True, eeg=True))

    assert result.tier_state.tier is Tier.T3_NEURAL, "the ceiling is unchanged by a stop"
    assert result.suppression_for(Claim.CUE_OPPORTUNITY).reason == Reason.CONSENT


# ------------------------------------------------------------------ baseline
def test_no_deviation_alert_before_the_baseline_is_established() -> None:
    engine = _engine()
    start = datetime.now(timezone.utc) - 60 * DAY

    for day in range(13):
        result = engine.ingest(_obs(start + day * DAY, phone=True))
        assert not result.emitted(Claim.DEVIATION)
        assert result.suppression_for(Claim.DEVIATION).reason == Reason.BASELINE

    assert not engine.twin.baseline.is_established


def test_the_baseline_establishes_and_then_deviation_becomes_available() -> None:
    engine = _engine()
    start = datetime.now(timezone.utc) - 60 * DAY

    for day in range(20):
        engine.ingest(_obs(start + day * DAY, phone=True))

    assert engine.twin.baseline.is_established
    later = engine.ingest(_obs(start + 20 * DAY, phone=True))
    reason = later.suppression_for(Claim.DEVIATION)
    assert reason is None or reason.reason != Reason.BASELINE


# ----------------------------------------------------------------- staleness
def test_a_gap_longer_than_the_freshness_window_is_flagged_and_withholds_deviation() -> None:
    engine = _engine()
    start = datetime.now(timezone.utc) - 60 * DAY

    for day in range(20):
        engine.ingest(_obs(start + day * DAY, phone=True))
    assert engine.twin.baseline.is_established

    after_gap = engine.ingest(_obs(start + 25 * DAY, phone=True))  # five days dark

    assert after_gap.stale
    assert not after_gap.emitted(Claim.CARE_PLAN)
    assert after_gap.suppression_for(Claim.DEVIATION).reason == Reason.STALE


def test_an_evaluation_that_receives_nothing_writes_nothing() -> None:
    """``as_of`` must keep meaning 'when data last arrived', not 'when we last looked'."""
    engine = _engine()
    at = datetime.now(timezone.utc) - 30 * DAY
    engine.ingest(_obs(at, phone=True))

    before = engine.twin.as_of
    writes = len(engine.twin.provenance)

    engine.ingest(Observation(patient_id="household-001", at=at + DAY))

    assert engine.twin.as_of == before
    assert len(engine.twin.provenance) == writes


# ---------------------------------------------------------------- provenance
def test_every_write_is_attributable_and_the_result_points_at_it() -> None:
    engine = _engine()
    at = datetime.now(timezone.utc) - 30 * DAY

    result = engine.ingest(_obs(at, phone=True, band=True))

    assert result.provenance_index is not None
    record = engine.twin.provenance[result.provenance_index]
    assert record.recorded_at == at
    assert record.fields_written, "a write with no recorded fields is not attributable"


# ------------------------------------------------------------------- outputs
def test_conversion_risk_is_refused_rather_than_guessed_when_no_model_is_present() -> None:
    engine = _engine()
    at = datetime.now(timezone.utc) - 30 * DAY

    result = engine.ingest(_obs(at, phone=True, band=True))

    assert not result.emitted(Claim.CONVERSION_RISK)
    assert result.suppression_for(Claim.CONVERSION_RISK).reason == Reason.NO_MODEL


def test_attribution_is_a_second_axis_the_ladder_cannot_satisfy_on_its_own() -> None:
    engine = _engine()
    at = datetime.now(timezone.utc) - 30 * DAY

    none = engine.ingest(_obs(at, phone=True, band=True, eeg=True))
    assert not none.tier_state.permits(Claim.DEVIATION_ATTRIBUTION)

    confirmed = Observation(
        patient_id="household-001",
        at=at + DAY,
        caregiver_report={"mood": "settled"},
        phone_ambient={"gait_speed": 1.1},
        wristband={"hrv_rmssd": 34.0},
        eeg={"theta_alpha_ratio": 1.4},
        attribution=AttributionBasis.A2_CONFIRMED,
    )
    assert engine.ingest(confirmed).tier_state.permits(Claim.DEVIATION_ATTRIBUTION)


def test_every_suppression_carries_a_reason() -> None:
    """'Why did nothing happen?' must always have an answer."""
    engine = _engine()
    at = datetime.now(timezone.utc) - 30 * DAY
    result = engine.ingest(_obs(at))

    assert result.suppressions
    for suppression in result.suppressions:
        assert suppression.reason
        assert suppression.claim in set(Claim)


@pytest.mark.parametrize(
    "claim,required",
    [
        (Claim.CARE_PLAN, Tier.T0_REPORT),
        (Claim.DEVIATION, Tier.T1_AMBIENT),
        (Claim.CONVERSION_RISK, Tier.T2_PHYSIOLOGICAL),
        (Claim.CUE_OPPORTUNITY, Tier.T3_NEURAL),
    ],
)
def test_each_claim_is_refused_one_tier_below_its_requirement(claim: Claim, required: Tier) -> None:
    if required is Tier.T0_REPORT:
        pytest.skip("T0 is the floor; there is no tier below it to test")

    engine = _engine()
    at = datetime.now(timezone.utc) - 30 * DAY
    below = Tier(required - 1)

    result = engine.ingest(
        _obs(
            at,
            phone=below >= Tier.T1_AMBIENT,
            band=below >= Tier.T2_PHYSIOLOGICAL,
            eeg=below >= Tier.T3_NEURAL,
        )
    )

    assert result.tier_state.tier is below
    assert not result.emitted(claim)
    assert result.suppression_for(claim).reason == Reason.CEILING
