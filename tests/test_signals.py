"""Edge-tier signal processing tests.

The important ones here are the quality-gate tests. They assert that the pipeline REFUSES to
produce features from unusable data rather than producing plausible-looking nonsense.
"""

from __future__ import annotations

import numpy as np
import pytest

from dte.config import MIN_USABLE_EPOCH_FRACTION
from dte.signals.eeg import extract_eeg_features, reject_artefacts
from dte.signals.gait import extract_gait_features
from dte.signals.hrv import _agitation_index, extract_hrv_features


class TestArtefactRejection:
    def test_clean_signal_mostly_survives(self, clean_eeg):
        raw, motion = clean_eeg
        clean, frac, n_valid = reject_artefacts(raw, motion_mask=motion)
        assert frac > 0.80
        assert n_valid >= 6
        assert clean.shape[0] > 0

    def test_heavily_contaminated_signal_is_mostly_rejected(self, dirty_eeg):
        raw, motion = dirty_eeg
        _, frac, _ = reject_artefacts(raw, motion_mask=motion)
        assert frac < MIN_USABLE_EPOCH_FRACTION

    def test_flatline_channel_is_detected(self, rng):
        raw = rng.normal(0, 10, (8, 2560))
        raw[3, :] = 0.0  # disconnected electrode
        _, _, n_valid = reject_artefacts(raw)
        assert n_valid == 7, "a disconnected electrode must be detected as invalid"

    def test_imu_gate_removes_epochs_on_independent_evidence(self, rng):
        raw = rng.normal(0, 10, (8, 256 * 20))
        n_epochs = (256 * 20) // int(2.0 * 256)
        motion = np.zeros(n_epochs, dtype=bool)
        motion[:5] = True
        _, frac_gated, _ = reject_artefacts(raw, motion_mask=motion)
        _, frac_ungated, _ = reject_artefacts(raw, motion_mask=None)
        assert frac_gated < frac_ungated

    def test_rejects_wrong_shape(self):
        with pytest.raises(ValueError, match="expected"):
            reject_artefacts(np.zeros(100))


class TestEEGQualityGate:
    """SAFETY PROPERTY: never infer from junk (docs/05 §5.7)."""

    def test_usable_signal_yields_features(self, clean_eeg):
        raw, motion = clean_eeg
        f = extract_eeg_features(raw, motion_mask=motion)
        assert f.quality == "sufficient"
        assert f.is_usable
        assert f.theta_alpha_ratio is not None
        total = sum(v for v in f.relative_power.values() if v is not None)
        assert abs(total - 1.0) < 1e-6, "relative power must sum to 1"

    def test_unusable_signal_returns_insufficient_and_no_features(self, dirty_eeg):
        raw, motion = dirty_eeg
        f = extract_eeg_features(raw, motion_mask=motion)
        assert f.quality == "insufficient"
        assert not f.is_usable
        assert f.theta_alpha_ratio is None, "must not fabricate a value from unusable data"
        assert f.relative_power == {}, "must not emit band powers below the quality gate"

    def test_empty_input_is_absent_not_zero(self):
        f = extract_eeg_features(np.empty((0, 0)))
        assert f.quality == "absent"
        assert not f.is_usable


class TestHRV:
    def test_calm_below_veto_and_agitated_above(self, calm_rr, agitated_rr):
        calm = extract_hrv_features(calm_rr)
        agitated = extract_hrv_features(agitated_rr)
        assert calm.is_usable and agitated.is_usable
        assert calm.agitation_index < 0.70, "calm state must not veto a cue"
        assert agitated.agitation_index > 0.70, "agitated state must veto a cue"
        assert agitated.rmssd_ms < calm.rmssd_ms, "agitation reduces variability"

    def test_low_beat_confidence_is_rejected(self, calm_rr):
        f = extract_hrv_features(calm_rr, beat_confidence=0.5)
        assert f.quality == "insufficient"
        assert f.agitation_index is None

    def test_too_few_beats_is_rejected(self):
        f = extract_hrv_features(np.array([800.0, 810.0, 795.0]))
        assert not f.is_usable

    def test_agitation_index_reachable_with_missing_channels(self):
        """SAFETY PROPERTY: an absent input must not disarm the veto.

        With fixed weights, a missing IMU channel plus a missing LF/HF channel would cap the index
        at 0.45 — below the 0.70 veto — making the veto structurally unreachable. Weights are
        renormalised over available channels precisely to prevent that.
        """
        assert _agitation_index(8.0, None, None) > 0.70
        assert _agitation_index(8.0, 5.0, None) > 0.70
        assert _agitation_index(44.0, None, None) < 0.70

    def test_agitation_index_is_bounded(self):
        assert 0.0 <= _agitation_index(0.0, 99.0, 1.0) <= 1.0
        assert 0.0 <= _agitation_index(999.0, 0.0, 0.0) <= 1.0


class TestGait:
    def test_short_bouts_are_insufficient(self, rng):
        f = extract_gait_features(
            stride_times_s=rng.normal(1.1, 0.1, 20),
            stride_lengths_m=rng.normal(1.2, 0.1, 20),
            bout_durations_s=np.array([5.0, 8.0]),  # both below the 30 s minimum
        )
        assert f.quality == "insufficient"
        assert f.gait_speed_ms is None, "must not compute speed from unqualifying bouts"

    def test_qualifying_bout_yields_speed(self, rng):
        f = extract_gait_features(
            stride_times_s=rng.normal(1.1, 0.05, 40),
            stride_lengths_m=rng.normal(1.2, 0.05, 40),
            bout_durations_s=np.array([45.0, 90.0]),
        )
        assert f.is_usable
        assert 0.5 < f.gait_speed_ms < 2.0
