"""Cue selection policy tests.

The reward-asymmetry tests are executable statements of a clinical judgement: upsetting someone is
worse than failing to help them.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dte.config import REWARD_DISTRESS, REWARD_RECALLED
from dte.policy.cue_selector import CueArm, CueSelector, Response, reward_for


class TestRewardAsymmetry:
    """SAFETY PROPERTY: the policy must be biased toward silence (ADR-0008)."""

    def test_distress_penalty_exceeds_recall_reward_in_magnitude(self):
        assert abs(REWARD_DISTRESS) > abs(REWARD_RECALLED), (
            "A symmetric reward drifts the policy toward firing more often under a noisy signal. "
            "This asymmetry is what makes it drift toward silence instead. Do not 'balance' these."
        )
        assert REWARD_DISTRESS < 0

    def test_reward_ordering(self):
        assert (
            reward_for(Response.DISTRESSED)
            < reward_for(Response.IGNORED)
            < reward_for(Response.ENGAGED)
            < reward_for(Response.RECALLED)
        )

    def test_unknown_response_is_missing_not_zero(self):
        """Imputing missing feedback as success teaches a system to fire constantly."""
        assert reward_for(Response.UNKNOWN) is None
        assert reward_for(Response.IGNORED) == 0.0, "ignored is a real zero, distinct from missing"


class TestSelection:
    def test_selects_an_available_arm(self):
        s = CueSelector(seed=1)
        sel = s.select("known-significant", 14)
        assert sel is not None
        assert sel.arm in list(CueArm)
        assert sel.context_key == "known-significant|afternoon"

    def test_context_discretisation(self):
        assert CueSelector.context_key("home", 9).endswith("morning")
        assert CueSelector.context_key("home", 14).endswith("afternoon")
        assert CueSelector.context_key("home", 20).endswith("evening")

    def test_learning_favours_the_rewarded_arm(self):
        s = CueSelector(epsilon=0.0, seed=1)  # pure exploitation
        for _ in range(12):
            sel = s.select("known-significant", 14, available_arms=[CueArm.PHOTO])
            s.update(sel, Response.RECALLED)
        for _ in range(12):
            sel = s.select("known-significant", 14, available_arms=[CueArm.SCENT])
            s.update(sel, Response.IGNORED)
        final = s.select("known-significant", 14)
        assert final.arm is CueArm.PHOTO

    def test_learning_is_per_context(self):
        s = CueSelector(epsilon=0.0, seed=1)
        sel = s.select("home", 9, available_arms=[CueArm.VOICE])
        s.update(sel, Response.RECALLED)
        snap = s.snapshot()
        assert snap["home|morning"]["voice"]["n"] == 1
        assert "known-significant|afternoon" not in snap

    def test_missing_feedback_does_not_update_the_arm(self):
        s = CueSelector(seed=1)
        sel = s.select("home", 14, available_arms=[CueArm.PHOTO])
        assert s.update(sel, Response.UNKNOWN) is None
        assert s.snapshot()["home|afternoon"]["photo"]["n"] == 0

    def test_snapshot_is_auditable(self):
        s = CueSelector(epsilon=0.0, seed=1)
        sel = s.select("home", 14, available_arms=[CueArm.PHOTO])
        s.update(sel, Response.ENGAGED)
        entry = s.snapshot()["home|afternoon"]["photo"]
        assert entry["n"] == 1
        assert abs(entry["value"] - 0.3) < 1e-9, "a clinician must be able to see the arm value"


class TestDistressSuppression:
    """SAFETY PROPERTY: the system retreats after distress rather than retrying."""

    def test_distress_suppresses_the_modality_for_24h(self):
        s = CueSelector(epsilon=0.0, seed=1)
        now = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        sel = s.select("home", 14, available_arms=[CueArm.PHOTO], now=now)
        s.update(sel, Response.DISTRESSED, now=now)

        blocked = s.select("home", 14, available_arms=[CueArm.PHOTO], now=now + timedelta(hours=1))
        assert blocked is None, "the distressing modality must be unavailable"

        later = s.select("home", 14, available_arms=[CueArm.PHOTO], now=now + timedelta(hours=25))
        assert later is not None, "suppression lifts after 24 hours"

    def test_distress_lowers_the_arm_value(self):
        s = CueSelector(epsilon=0.0, seed=1)
        now = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        sel = s.select("home", 14, available_arms=[CueArm.PHOTO], now=now)
        reward = s.update(sel, Response.DISTRESSED, now=now)
        assert reward == REWARD_DISTRESS
        assert s.snapshot()["home|afternoon"]["photo"]["value"] < 0

    def test_other_modalities_remain_available_after_distress(self):
        s = CueSelector(epsilon=0.0, seed=1)
        now = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        sel = s.select("home", 14, available_arms=[CueArm.PHOTO], now=now)
        s.update(sel, Response.DISTRESSED, now=now)
        other = s.select("home", 14, available_arms=[CueArm.VOICE], now=now)
        assert other is not None and other.arm is CueArm.VOICE
