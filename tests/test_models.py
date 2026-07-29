"""Risk model and trajectory tests.

The explanation-coverage tests encode ADR-0006: a score cannot exist without its reasoning, and
there is no bypass path.
"""

from __future__ import annotations

import numpy as np
import pytest

from dte.config import MIN_EXPLANATION_FEATURES
from dte.models.decline import DeviationDetector, forecast_trajectory
from dte.models.risk import Explanation, RiskModel, RiskOutput
from dte.twin import Baseline


class TestExplanationIsMandatory:
    """SAFETY PROPERTY: ADR-0006 — no score without reasoning."""

    def test_risk_output_rejects_too_few_features(self):
        with pytest.raises(ValueError, match="ADR-0006"):
            RiskOutput(
                score=0.7,
                band="elevated",
                top_features=[Explanation("theta_relative_power", 0.2, "increases-risk")],
            )

    def test_risk_output_accepts_the_minimum(self):
        out = RiskOutput(
            score=0.7,
            band="elevated",
            top_features=[
                Explanation(f"f{i}", 0.1, "increases-risk") for i in range(MIN_EXPLANATION_FEATURES)
            ],
        )
        assert len(out.top_features) == MIN_EXPLANATION_FEATURES


class TestRiskModel:
    def test_fit_and_predict_with_reasoning(self, cohort):
        X, y, _ = cohort.to_arrays()
        m = RiskModel().fit(X, y, cohort.feature_names)
        out = m.predict(cohort.patients[0].features)
        assert 0.0 <= out.score <= 1.0
        assert out.band in {"low", "moderate", "elevated"}
        assert len(out.top_features) >= MIN_EXPLANATION_FEATURES
        assert all(f.plain_language for f in out.top_features), (
            "an explanation a clinician cannot read is not an explanation"
        )

    def test_predict_before_fit_raises(self, cohort):
        with pytest.raises(RuntimeError, match="before fit"):
            RiskModel().predict(cohort.patients[0].features)

    def test_missing_features_are_not_imputed(self, cohort):
        """docs/05 §5.7 — insufficient means insufficient."""
        X, y, _ = cohort.to_arrays()
        m = RiskModel().fit(X, y, cohort.feature_names)
        bad = dict(cohort.patients[0].features)
        bad["theta_relative_power"] = None
        with pytest.raises(ValueError, match="insufficient data"):
            m.predict(bad)

    def test_feature_name_mismatch_raises(self, cohort):
        X, y, _ = cohort.to_arrays()
        with pytest.raises(ValueError):
            RiskModel().fit(X, y, cohort.feature_names[:-1])

    def test_patient_facing_summary_avoids_diagnostic_language(self, cohort):
        X, y, _ = cohort.to_arrays()
        m = RiskModel().fit(X, y, cohort.feature_names)
        text = m.predict(cohort.patients[0].features).patient_facing_summary()
        assert "not a diagnosis" in text.lower()
        assert "stop using this tool" in text.lower(), "the person must be told they can opt out"

    def test_learns_the_synthetic_signal(self, cohort):
        """Sanity check only. Accuracy here reflects the generator's assumptions, not biology."""
        X, y, _ = cohort.to_arrays()
        split = int(0.75 * len(y))
        m = RiskModel().fit(X[:split], y[:split], cohort.feature_names)
        acc = float(np.mean(m.model.predict(X[split:]) == y[split:]))
        assert acc > 0.60


class TestTrajectory:
    def test_two_points_suppresses_the_point_estimate(self):
        """SAFETY PROPERTY: no confident-looking forecast the model cannot support."""
        f = forecast_trajectory([0.0, 6.0], [26.0, 24.0])
        assert f.point_estimate_suppressed
        assert f.to_dict()["projected_values"] is None
        assert f.ci_lower and f.ci_upper

    def test_single_point_produces_no_forecast(self):
        f = forecast_trajectory([0.0], [26.0])
        assert f.point_estimate_suppressed
        assert f.n_anchors == 1
        assert "Fewer than 2" in f.note

    def test_dense_consistent_history_yields_a_usable_forecast(self):
        times = list(np.arange(0, 36, 3.0))
        values = [26.0 - 0.18 * t for t in times]
        f = forecast_trajectory(times, values)
        assert not f.point_estimate_suppressed
        assert f.confidence > 0.0
        assert len(f.projected_values) == 12

    def test_interval_always_present(self):
        f = forecast_trajectory([0.0, 6.0, 12.0], [26.0, 25.0, 23.5])
        assert len(f.ci_lower) == len(f.ci_upper) == 12
        assert all(lo < hi for lo, hi in zip(f.ci_lower, f.ci_upper))

    def test_interval_widens_with_horizon(self):
        f = forecast_trajectory([0.0, 6.0, 12.0], [26.0, 25.0, 23.5])
        first = f.ci_upper[0] - f.ci_lower[0]
        last = f.ci_upper[-1] - f.ci_lower[-1]
        assert last > first, "uncertainty must grow with distance from observed data"


class TestDeviationDetection:
    @staticmethod
    def _established_baseline(values: list[float]) -> Baseline:
        from datetime import datetime, timedelta, timezone

        b = Baseline()
        start = datetime.now(timezone.utc) - timedelta(days=40)
        for i, v in enumerate(values):
            b.update({"gait_speed_ms": v}, at=start + timedelta(days=i))
        return b

    def test_no_alert_before_baseline_established(self):
        """SAFETY PROPERTY: no alerting in week one."""
        b = Baseline()
        b.update({"gait_speed_ms": 1.10})
        r = DeviationDetector().evaluate("gait_speed_ms", [0.70], b)
        assert not r.deviated
        assert "not established" in r.detail.lower()

    def test_sustained_deviation_is_detected(self):
        b = self._established_baseline([1.10 + 0.02 * ((-1) ** i) for i in range(30)])
        r = DeviationDetector().evaluate("gait_speed_ms", [0.72, 0.70, 0.71, 0.69], b)
        assert r.deviated
        assert r.robust_z is not None and r.robust_z < 0
        assert r.sustained_days >= 3

    def test_single_outlier_is_not_an_alert(self):
        b = self._established_baseline([1.10 + 0.02 * ((-1) ** i) for i in range(30)])
        r = DeviationDetector().evaluate("gait_speed_ms", [1.11, 1.09, 1.10, 0.70], b)
        assert not r.deviated, "one bad reading must not raise an alert"

    def test_unknown_feature_is_handled(self):
        b = self._established_baseline([1.1] * 30)
        r = DeviationDetector().evaluate("nonexistent", [1.0], b)
        assert not r.deviated
