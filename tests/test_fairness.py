"""Subgroup fairness gate tests.

These encode ADR-0007. The second test class is the one that matters most: "cannot certify" must
block a release just as firmly as a measured gap does.
"""

from __future__ import annotations

import numpy as np

from dte.config import MAX_SUBGROUP_GAP, MIN_SUBGROUP_N
from dte.data.synthetic import generate_cohort
from dte.fairness.subgroup import evaluate_fairness
from dte.models.risk import RiskModel


def _run(noise: float, n: int = 600):
    cohort = generate_cohort(n=n, underrepresented_noise_multiplier=noise, seed=42)
    X, y, attributes = cohort.to_arrays()
    split = int(0.7 * len(y))
    m = RiskModel().fit(X[:split], y[:split], cohort.feature_names)
    y_pred = m.model.predict(X[split:])
    return evaluate_fairness(y[split:], y_pred, {k: v[split:] for k, v in attributes.items()})


class TestGapDetection:
    def test_gate_computes_a_gap_and_names_the_group(self):
        r = _run(noise=3.0)
        assert r.max_gap is not None
        assert r.max_gap_group is not None
        assert r.population_accuracy is not None

    def test_large_gap_blocks_release(self):
        y_true = np.array([1, 0] * 60)
        # Group B is predicted wrongly far more often than group A.
        y_pred = np.array([1, 0] * 45 + [0, 1] * 15)
        groups = ["A"] * 90 + ["B"] * 30
        r = evaluate_fairness(y_true, y_pred, {"race_ethnicity": groups})
        assert not r.passed
        assert r.max_gap > MAX_SUBGROUP_GAP
        assert any("exceeds" in b for b in r.blocking_reasons)

    def test_remediation_rejects_waiting_for_more_data(self):
        y_true = np.array([1, 0] * 60)
        y_pred = np.array([1, 0] * 45 + [0, 1] * 15)
        groups = ["A"] * 90 + ["B"] * 30
        r = evaluate_fairness(y_true, y_pred, {"race_ethnicity": groups})
        text = " ".join(r.remediation).lower()
        assert "rebalance" in text
        assert "do not wait" in text, (
            "the gap does not close as datasets grow — remediation must say so"
        )

    def test_equal_performance_passes(self):
        y_true = np.array([1, 0] * 60)
        y_pred = y_true.copy()
        groups = ["A"] * 60 + ["B"] * 60
        r = evaluate_fairness(y_true, y_pred, {"sex": groups})
        assert r.passed
        assert r.max_gap == 0.0


class TestUncertifiableBlocksToo:
    """SAFETY PROPERTY: "not enough data to check" must block the release (ADR-0007 rule 2)."""

    def test_small_subgroup_blocks_release(self):
        y_true = np.array([1, 0] * 50)
        y_pred = y_true.copy()  # perfect predictions — the ONLY problem is subgroup size
        groups = ["A"] * 95 + ["B"] * 5  # B has n=5, far below the minimum
        r = evaluate_fairness(y_true, y_pred, {"race_ethnicity": groups})
        assert not r.passed, (
            "a perfectly accurate model must still be blocked when a subgroup cannot be certified. "
            "Shipping uncertified and assuming it is fine is how gaps reach production."
        )
        assert r.uncertifiable
        assert any("cannot be certified" in b for b in r.blocking_reasons)

    def test_uncertifiable_subgroup_has_no_fabricated_metrics(self):
        y_true = np.array([1, 0] * 50)
        y_pred = y_true.copy()
        groups = ["A"] * 95 + ["B"] * 5
        r = evaluate_fairness(y_true, y_pred, {"race_ethnicity": groups})
        small = [s for s in r.subgroups if s.group == "B"][0]
        assert not small.certifiable
        assert small.accuracy is None, "must not report a metric it cannot certify"
        assert small.n < MIN_SUBGROUP_N

    def test_remediation_offers_narrowing_the_population_in_writing(self):
        y_true = np.array([1, 0] * 50)
        y_pred = y_true.copy()
        groups = ["A"] * 95 + ["B"] * 5
        r = evaluate_fairness(y_true, y_pred, {"race_ethnicity": groups})
        text = " ".join(r.remediation).lower()
        assert "narrow" in text and "writing" in text


class TestReportShape:
    def test_report_serialises(self):
        r = _run(noise=2.5)
        d = r.to_dict()
        assert set(d) >= {"passed", "max_gap", "threshold", "subgroups", "blocking_reasons"}
        assert isinstance(d["subgroups"], list)

    def test_summary_states_the_verdict(self):
        r = _run(noise=2.5)
        assert ("PASSED" in r.summary()) or ("BLOCKED" in r.summary())

    def test_all_expected_attributes_are_evaluated(self):
        r = _run(noise=2.0)
        assert {s.attribute for s in r.subgroups} >= {
            "age_band",
            "sex",
            "race_ethnicity",
            "primary_language",
            "education_band",
            "site",
        }
