"""Twin state store tests — personal baseline, consent gating, provenance."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dte.config import BASELINE_MIN_DAYS
from dte.twin import Baseline, ConsentSnapshot, RollingStat, TwinState


def _utc(days_ago: float = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


class TestRollingStat:
    def test_accumulates_statistics(self):
        s = RollingStat()
        for v in [1.0, 2.0, 3.0, 4.0, 5.0]:
            s.update(v)
        assert s.n == 5
        assert abs(s.mean - 3.0) < 1e-9
        assert abs(s.median - 3.0) < 1e-9
        assert s.std > 0

    def test_z_score_needs_variance(self):
        s = RollingStat()
        s.update(5.0)
        assert s.z_score(9.0) is None, "cannot z-score against a single observation"

    def test_robust_z_resists_outliers(self):
        s = RollingStat()
        for v in [1.0 + 0.05 * ((-1) ** i) for i in range(20)] + [500.0]:  # one wild outlier
            s.update(v)
        # The outlier inflates the standard deviation, shrinking the standard z-score. The MAD
        # barely moves, so the robust z-score still registers a genuine departure.
        assert abs(s.robust_z(2.0)) > abs(s.z_score(2.0))

    def test_robust_z_falls_back_when_mad_is_zero(self):
        """KNOWN LIMITATION, asserted so it stays visible: a degenerate baseline (>half the
        observations identical) has MAD 0 and loses outlier resistance."""
        s = RollingStat()
        for _ in range(20):
            s.update(1.0)
        s.update(500.0)
        assert s.mad == 0.0
        assert s.robust_z(2.0) == s.z_score(2.0)

    def test_ignores_none(self):
        s = RollingStat()
        s.update(1.0)
        s.update(None)  # type: ignore[arg-type]
        assert s.n == 1


class TestBaseline:
    def test_not_established_initially(self):
        b = Baseline()
        assert not b.is_established

    def test_established_after_minimum_period(self):
        b = Baseline()
        start = _utc(days_ago=BASELINE_MIN_DAYS + 5)
        for i in range(BASELINE_MIN_DAYS + 2):
            b.update({"gait_speed_ms": 1.1}, at=start + timedelta(days=i))
        assert b.is_established
        assert b.established_at is not None

    def test_not_established_with_few_observations_over_long_span(self):
        b = Baseline()
        b.update({"gait_speed_ms": 1.1}, at=_utc(days_ago=100))
        b.update({"gait_speed_ms": 1.1}, at=_utc(days_ago=1))
        assert not b.is_established, "a long span with 2 points is not an established baseline"

    def test_deviation_is_relative_to_this_patient(self):
        """Principle P1 — the same value is normal for one person and alarming for another."""
        slow = Baseline()
        fast = Baseline()
        start = _utc(days_ago=40)
        for i in range(30):
            slow.update({"gait_speed_ms": 0.95 + 0.01 * ((-1) ** i)}, at=start + timedelta(days=i))
            fast.update({"gait_speed_ms": 1.40 + 0.01 * ((-1) ** i)}, at=start + timedelta(days=i))
        value = 0.95
        assert abs(slow.deviation("gait_speed_ms", value)) < 2.0, "normal for the slower walker"
        assert abs(fast.deviation("gait_speed_ms", value)) > 5.0, "alarming for the faster walker"


class TestConsent:
    def test_everything_defaults_to_false(self):
        c = ConsentSnapshot()
        assert not c.neural_data
        assert not c.location_data
        assert not c.cue_delivery
        assert not c.family_visibility
        assert not c.federated_participation

    def test_patient_stop_overrides_active_consent(self):
        """docs/10 §10.1 — the person can say stop, and stop means stop."""
        now = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
        c = ConsentSnapshot(cue_delivery=True, patient_stop_until=now + timedelta(hours=24))
        assert not c.permits_cue(now=now)
        assert not c.permits_cue(now=now + timedelta(hours=23))
        assert c.permits_cue(now=now + timedelta(hours=25))

    def test_consent_gates_reads_not_just_display(self):
        t = TwinState(patient_id="p1")
        t.consent.neural_data = True
        assert t.readable("neural_data")
        assert not t.readable("location_data"), (
            "withdrawn consent makes features unreadable, not merely hidden in the UI"
        )


class TestTwinState:
    def test_apply_records_provenance(self):
        t = TwinState(patient_id="p1")
        t.apply(
            neural={"theta_relative_power": 0.24},
            source="eeg-headband",
            consent_basis="TREAT",
            device_id="EEG-HB-0042",
            transform_version="dte-signals-eeg-0.1.0",
        )
        assert len(t.provenance) == 1
        p = t.provenance[0]
        assert p.source == "eeg-headband"
        assert p.device_id == "EEG-HB-0042"
        assert p.consent_basis == "TREAT"
        assert "neural.theta_relative_power" in p.fields_written

    def test_every_write_appends_provenance(self):
        t = TwinState(patient_id="p1")
        for _ in range(4):
            t.apply(mobility={"gait_speed_ms": 1.1}, source="wristband")
        assert len(t.provenance) == 4

    def test_stale_when_no_recent_data(self):
        t = TwinState(patient_id="p1", as_of=_utc(days_ago=5))
        assert t.is_stale()

    def test_fresh_twin_is_not_stale(self):
        assert not TwinState(patient_id="p1").is_stale()

    def test_cannot_alert_before_baseline_established(self):
        t = TwinState(patient_id="p1")
        t.apply(mobility={"gait_speed_ms": 1.1}, source="wristband")
        assert not t.can_alert()

    def test_cannot_alert_when_stale(self):
        t = TwinState(patient_id="p1")
        start = _utc(days_ago=100)
        for i in range(30):
            t.apply(mobility={"gait_speed_ms": 1.1}, source="w", at=start + timedelta(days=i))
        assert t.baseline.is_established
        assert not t.can_alert(), "an established baseline is not enough if the twin is stale"

    def test_serialises_to_schema_shape(self):
        t = TwinState(patient_id="p1")
        t.apply(neural={"theta_relative_power": 0.24}, source="eeg")
        d = t.to_dict()
        assert d["patient_id"] == "p1"
        assert "is_stale" in d
        assert "is_established" in d["baseline"]
        assert isinstance(d["as_of"], str), "datetimes must serialise to ISO strings"
        assert "_values" not in str(d), "internal buffers must not leak into the export"
