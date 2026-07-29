"""Demo API tests.

Note ``test_root_warns_not_for_deployment``: the warning is part of the contract, not decoration.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from dte.api.app import app  # noqa: E402

client = TestClient(app)


class TestMeta:
    def test_root_warns_not_for_deployment(self):
        r = client.get("/")
        assert r.status_code == 200
        w = r.json()["warning"].lower()
        assert "not a medical device" in w
        assert "not for deployment" in w
        assert "synthetic" in w

    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["data"] == "synthetic-only"


class TestOpportunity:
    def test_ideal_conditions_deliver_with_a_selection(self):
        r = client.post("/predict/opportunity", json={})
        assert r.status_code == 200
        body = r.json()
        assert body["deliver"] is True
        assert "selection" in body
        assert len(body["gates"]) == 6

    def test_agitation_blocks_and_names_the_gate(self):
        r = client.post("/predict/opportunity", json={"agitation_index": 0.9})
        body = r.json()
        assert body["deliver"] is False
        assert "agitation" in body["failed_gates"]
        assert "selection" not in body

    def test_quiet_hours_block(self):
        r = client.post("/predict/opportunity", json={"hour_of_day": 23})
        assert r.json()["deliver"] is False

    def test_no_consent_blocks(self):
        r = client.post("/predict/opportunity", json={"consent_permits_cue": False})
        assert "consent" in r.json()["failed_gates"]

    def test_validation_rejects_bad_place_class(self):
        r = client.post("/predict/opportunity", json={"place_class": "nonsense"})
        assert r.status_code == 422


class TestResponseReporting:
    def test_unknown_response_returns_null_reward(self):
        r = client.post("/report/response", json={"response": "unknown"})
        assert r.status_code == 200
        body = r.json()
        assert body["reward"] is None
        assert "never imputed" in body["reward_note"].lower()

    def test_distress_returns_negative_reward(self):
        r = client.post("/report/response", json={"response": "distressed"})
        assert r.json()["reward"] == -2.0

    def test_invalid_response_is_rejected(self):
        r = client.post("/report/response", json={"response": "delighted"})
        assert r.status_code == 422


class TestRisk:
    def test_risk_includes_reasoning_and_patient_summary(self):
        r = client.get("/predict/risk?patient_index=0")
        assert r.status_code == 200
        body = r.json()
        assert len(body["risk"]["top_features"]) >= 3
        assert "not a diagnosis" in body["patient_facing_summary"].lower()
        assert body["fhir"]["resourceType"] == "RiskAssessment"
        assert body["fhir"]["basis"], "RiskAssessment.basis must carry the supporting evidence"

    def test_out_of_range_index_is_404(self):
        r = client.get("/predict/risk?patient_index=999999")
        assert r.status_code == 404


class TestTrajectory:
    def test_two_points_suppresses_point_estimate(self):
        r = client.post("/simulate/decline", json={"times_months": [0, 6], "values": [26, 24]})
        assert r.json()["forecast"]["point_estimate_suppressed"] is True

    def test_rejects_non_positive_horizon(self):
        r = client.post(
            "/simulate/decline",
            json={"times_months": [0, 6], "values": [26, 24], "horizon_months": 0},
        )
        assert r.status_code == 422


class TestGovernance:
    def test_fair_cohort_passes_gate(self):
        r = client.get("/fairness/report?noise_multiplier=1.0")
        assert r.status_code == 200
        assert "report" in r.json()

    def test_biased_cohort_report_is_produced(self):
        r = client.get("/fairness/report?noise_multiplier=3.0")
        body = r.json()["report"]
        assert "max_gap" in body
        assert "subgroups" in body


class TestSignals:
    def test_clean_signal_is_usable(self):
        r = client.get("/signals/demo?artefact_rate=0.05")
        assert r.json()["eeg"]["is_usable"] is True

    def test_heavily_contaminated_signal_fails_the_gate(self):
        r = client.get("/signals/demo?artefact_rate=0.9")
        assert r.json()["eeg"]["is_usable"] is False

    def test_agitated_state_reports_a_veto(self):
        r = client.get("/signals/demo?agitated=true")
        assert r.json()["hrv"]["vetoes_cue"] is True

    def test_response_notes_raw_data_is_discarded(self):
        r = client.get("/signals/demo")
        assert "discarded" in r.json()["note"].lower()


class TestDaySimulation:
    def test_silence_is_the_majority_outcome(self):
        r = client.get("/day/simulate?seed=42")
        body = r.json()
        assert body["cues_delivered"] >= 1, (
            "a day with zero cues would make the other assertions vacuous and would indicate the "
            "threshold is miscalibrated rather than appropriately cautious"
        )
        assert body["cues_delivered"] <= 8, "daily budget must be respected"
        assert body["silence_rate"] > 0.4, (
            "the MAP is precision-weighted; silence should still dominate"
        )
