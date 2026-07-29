"""Data-driven conformance suite for the fidelity ladder.

Every case here is loaded from ``tests/fixtures/tier_scenarios.json`` rather than written in
Python. That separation is deliberate and has three purposes:

* **The scenarios outlive this implementation.** Any future re-implementation — a different
  language, a vendor integration, a replication by another group — can be checked against the same
  file without reading this codebase.
* **Clinicians can review them.** Each scenario carries a narrative and a ``why_it_matters`` field.
  A nurse-navigator can read the JSON and tell us a scenario is wrong, which is not true of
  ``@pytest.mark.parametrize``.
* **They double as documentation and demo input.** The same file backs
  ``docs/15-fidelity-ladder.md`` and can be replayed by the CLI.

If a scenario fails, the question is whether the scenario is wrong or the code is. Both are
possible, and neither should be changed without saying which.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dte.tiers import (
    Claim,
    ClaimCeilingViolation,
    Tier,
    assert_claim_permitted,
    detect_tier,
    downgrade_note,
)

FIXTURE = Path(__file__).parent / "fixtures" / "tier_scenarios.json"


def _load() -> dict:
    with FIXTURE.open(encoding="utf-8") as fh:
        return json.load(fh)


DATA = _load()
SCENARIOS = DATA["scenarios"]
IDS = [s["id"] for s in SCENARIOS]


# ---------------------------------------------------------------------------
# Fixture integrity — a broken scenario file must fail loudly, not skip silently
# ---------------------------------------------------------------------------


def test_fixture_loads_and_is_non_empty():
    assert SCENARIOS, "tier_scenarios.json contains no scenarios"
    assert len(IDS) == len(set(IDS)), "duplicate scenario ids"


def test_every_declared_tier_matches_the_implementation():
    """The JSON tier table and ``dte.tiers`` must not drift apart."""
    for name, spec in DATA["tiers"].items():
        assert hasattr(Tier, name), f"fixture declares unknown tier {name}"
        assert int(getattr(Tier, name)) == spec["ordinal"]


def test_every_scenario_declares_expected_tier_and_claims():
    for s in SCENARIOS:
        assert s["expected_tier"] in DATA["tiers"], s["id"]
        for c in s.get("permitted", []) + s.get("forbidden", []):
            assert hasattr(Claim, c), f"{s['id']} references unknown claim {c}"
        assert s.get("narrative"), f"{s['id']} has no narrative"
        assert s.get("why_it_matters"), f"{s['id']} does not say why it matters"


# ---------------------------------------------------------------------------
# The scenarios themselves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_scenario_yields_expected_tier(scenario):
    state = detect_tier(scenario["signals"])
    expected = getattr(Tier, scenario["expected_tier"])
    assert state.tier is expected, (
        f"{scenario['id']} ({scenario['name']}): expected {expected.name}, "
        f"got {state.tier.name}. {scenario['why_it_matters']}"
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_scenario_permits_exactly_what_it_should(scenario):
    state = detect_tier(scenario["signals"])
    for name in scenario.get("permitted", []):
        assert_claim_permitted(state, getattr(Claim, name))


@pytest.mark.parametrize("scenario", SCENARIOS, ids=IDS)
def test_scenario_forbids_exactly_what_it_should(scenario):
    state = detect_tier(scenario["signals"])
    for name in scenario.get("forbidden", []):
        claim = getattr(Claim, name)
        with pytest.raises(ClaimCeilingViolation):
            assert_claim_permitted(state, claim)


@pytest.mark.parametrize(
    "scenario", [s for s in SCENARIOS if "missing_for_next" in s],
    ids=[s["id"] for s in SCENARIOS if "missing_for_next" in s],
)
def test_scenario_reports_what_blocks_the_next_tier(scenario):
    state = detect_tier(scenario["signals"])
    assert sorted(state.missing_for_next) == sorted(scenario["missing_for_next"])


@pytest.mark.parametrize(
    "scenario", [s for s in SCENARIOS if "expect_unknown" in s],
    ids=[s["id"] for s in SCENARIOS if "expect_unknown" in s],
)
def test_scenario_records_unrecognised_signals(scenario):
    state = detect_tier(scenario["signals"])
    for name in scenario["expect_unknown"]:
        assert name in state.unknown
        assert name in state.explain()


# ---------------------------------------------------------------------------
# Transitions — scenarios that declare a previous state
# ---------------------------------------------------------------------------

TRANSITIONS = [s for s in SCENARIOS if "previous_signals" in s]


@pytest.mark.parametrize(
    "scenario", TRANSITIONS, ids=[s["id"] for s in TRANSITIONS]
)
def test_scenario_transition_emits_the_right_note(scenario):
    previous = detect_tier(scenario["previous_signals"])
    current = detect_tier(scenario["signals"])
    note = downgrade_note(previous, current)

    if scenario.get("expect_downgrade_note"):
        assert note is not None, f"{scenario['id']}: expected a downgrade note, got none"
        for fragment in scenario.get("downgrade_note_contains", []):
            assert fragment.lower() in note.lower(), (
                f"{scenario['id']}: downgrade note missing '{fragment}'. Note was: {note}"
            )
    else:
        assert note is None, f"{scenario['id']}: expected no downgrade note, got: {note}"


# ---------------------------------------------------------------------------
# Coverage — the suite must exercise every tier and every claim
# ---------------------------------------------------------------------------


def test_scenarios_cover_every_tier():
    covered = {s["expected_tier"] for s in SCENARIOS}
    assert covered == set(DATA["tiers"]), f"tiers never exercised: {set(DATA['tiers']) - covered}"


def test_scenarios_cover_every_claim_in_both_directions():
    permitted = {c for s in SCENARIOS for c in s.get("permitted", [])}
    forbidden = {c for s in SCENARIOS for c in s.get("forbidden", [])}
    all_claims = {c.name for c in Claim}
    assert all_claims - permitted == set(), f"never permitted anywhere: {all_claims - permitted}"
    assert all_claims - forbidden == set(), f"never forbidden anywhere: {all_claims - forbidden}"
