"""Opportunity detector tests — the hard gates and the agitation veto.

These encode the central safety asymmetry of the Memory Anchoring Pipeline: elevated agitation
BLOCKS a cue outright rather than lowering a score that a strong neural signal could outvote.
"""

from __future__ import annotations

import pytest

from dte.config import AlertBudgetConfig
from dte.fusion.detector import Alert, AlertBudget, FusionInput, OpportunityDetector


def ideal_input(**overrides) -> FusionInput:
    """A configuration that should deliver, so each test can break exactly one thing."""
    base = dict(
        place_class="known-significant",
        place_significance=0.90,
        hour_of_day=14,
        agitation_index=0.24,
        theta_alpha_z=1.8,
        eligible_content_count=3,
        signal_quality=0.90,
        minutes_since_last_cue=71.0,
        cues_delivered_today=2,
        consent_permits_cue=True,
    )
    base.update(overrides)
    return FusionInput(**base)


class TestBaseline:
    def test_ideal_conditions_deliver(self):
        d = OpportunityDetector().decide(ideal_input())
        assert d.deliver
        assert d.confidence >= d.threshold
        assert d.failed_gates == []


class TestAgitationVeto:
    """SAFETY PROPERTY: agitation is a veto, not a weighted vote (docs/03 §3.3)."""

    def test_high_agitation_blocks_even_with_maximal_confidence(self):
        d = OpportunityDetector().decide(
            ideal_input(
                agitation_index=0.85,
                theta_alpha_z=3.0,  # strongest possible neural signal
                place_significance=1.0,  # strongest possible context
                eligible_content_count=10,
                signal_quality=1.0,
            )
        )
        assert not d.deliver
        assert "agitation" in d.failed_gates
        assert d.confidence > d.threshold, (
            "the point of this test: confidence was ABOVE threshold and the cue was still blocked. "
            "A weighted-vote design would have fired here."
        )

    def test_unknown_agitation_fails_closed(self):
        d = OpportunityDetector().decide(ideal_input(agitation_index=None))
        assert not d.deliver
        assert "agitation" in d.failed_gates


class TestHardGates:
    def test_refractory_period(self):
        d = OpportunityDetector().decide(ideal_input(minutes_since_last_cue=10.0))
        assert not d.deliver and "refractory" in d.failed_gates

    def test_first_ever_cue_is_not_blocked_by_refractory(self):
        d = OpportunityDetector().decide(ideal_input(minutes_since_last_cue=None))
        assert "refractory" not in d.failed_gates

    @pytest.mark.parametrize("hour", [22, 23, 0, 3, 6])
    def test_quiet_hours_block(self, hour):
        d = OpportunityDetector().decide(ideal_input(hour_of_day=hour))
        assert not d.deliver and "quiet_hours" in d.failed_gates

    def test_no_consent_blocks(self):
        d = OpportunityDetector().decide(ideal_input(consent_permits_cue=False))
        assert not d.deliver and "consent" in d.failed_gates

    def test_low_signal_quality_blocks(self):
        d = OpportunityDetector().decide(ideal_input(signal_quality=0.4))
        assert not d.deliver and "quality" in d.failed_gates

    def test_daily_budget_exhausted_blocks(self):
        d = OpportunityDetector().decide(ideal_input(cues_delivered_today=8))
        assert not d.deliver and "daily_budget" in d.failed_gates

    def test_all_six_gates_are_evaluated(self):
        d = OpportunityDetector().decide(ideal_input())
        assert {g.name for g in d.gates} == {
            "agitation",
            "refractory",
            "quiet_hours",
            "consent",
            "quality",
            "daily_budget",
        }


class TestSilenceIsDefault:
    def test_no_content_means_silence(self):
        """There is no generic fallback content (docs/04 §4.4)."""
        d = OpportunityDetector().decide(ideal_input(eligible_content_count=0))
        assert not d.deliver

    def test_novel_place_scores_low_not_high(self):
        """Novelty is disorienting. This is not a tour guide."""
        novel = OpportunityDetector().decide(
            ideal_input(place_class="novel", place_significance=None)
        )
        significant = OpportunityDetector().decide(
            ideal_input(place_class="known-significant", place_significance=None)
        )
        assert novel.channel_scores["context"] < significant.channel_scores["context"]

    def test_silence_records_a_reason(self):
        d = OpportunityDetector().decide(ideal_input(agitation_index=0.9))
        assert d.reason, "silence must be a logged decision, not an absence of behaviour"
        assert "SILENT" in d.explain()

    def test_poor_quality_attenuates_confidence(self):
        high = OpportunityDetector().decide(ideal_input(signal_quality=1.0))
        low = OpportunityDetector().decide(ideal_input(signal_quality=0.65))
        assert low.confidence < high.confidence


class TestAlertBudget:
    def test_delivers_up_to_the_agreed_ceiling(self):
        b = AlertBudget(AlertBudgetConfig(weekly_ceiling=3))
        results = [b.submit(Alert(patient_id=f"p{i}", driver="gait-decline")) for i in range(5)]
        assert results == [True, True, True, False, False]
        assert len(b.suppressed) == 2

    def test_deduplicates_same_patient_same_driver(self):
        b = AlertBudget(AlertBudgetConfig(weekly_ceiling=10))
        assert b.submit(Alert(patient_id="p1", driver="gait-decline")) is True
        assert b.submit(Alert(patient_id="p1", driver="gait-decline")) is False
        assert b.submit(Alert(patient_id="p1", driver="hrv-change")) is True

    def test_suppression_is_auditable(self):
        b = AlertBudget(AlertBudgetConfig(weekly_ceiling=1))
        b.submit(Alert(patient_id="p1", driver="a"))
        b.submit(Alert(patient_id="p2", driver="b"))
        r = b.suppression_report()
        assert r["suppressed"] == 1
        assert r["action_required"] is True
        assert "b" in r["suppressed_drivers"]
        assert "renegotiate" in str(r["note"]).lower()

    def test_ceiling_must_be_positive(self):
        with pytest.raises(ValueError):
            AlertBudgetConfig(weekly_ceiling=0)
