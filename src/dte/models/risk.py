"""MCI-to-dementia risk stratification via a tree ensemble.

Implements ``docs/03-digital-twin-engine.md`` §3.5, ``docs/06-ml-architecture.md`` §6.4 and
``docs/adr/0004-ensembles-over-deep-networks.md``.

WHY TREE ENSEMBLES AND NOT A DEEP NETWORK
-----------------------------------------
Two criteria outrank raw accuracy here (ADR-0004):

* **Interpretability.** A clinician who cannot see why a model reached its conclusion will not act
  on it. Native feature importances give explainability for free.
* **Computational footprint.** A model needing a GPU cluster is not an option for many community
  health systems. Since the populations that most need this are where resources are thinnest, a
  GPU requirement is an equity constraint, not just a technical one. Target envelope: 4 vCPU,
  16 GB RAM, no GPU.

We are probably leaving accuracy on the table. That is accepted knowingly.

HARD OUTPUT CONTRACT (ADR-0006)
-------------------------------
``predict`` REFUSES to return a score without at least ``MIN_EXPLANATION_FEATURES`` ranked
contributing features. There is no bypass. A score without reasoning gets ignored by clinicians
and is unsafe besides — a clinician who can see the reasoning can catch a model relying on
something spurious.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier

from dte.config import MIN_EXPLANATION_FEATURES
from dte.tiers import Claim, TierState, assert_claim_permitted

MODEL_VERSION = "risk-ensemble-0.1.0"

# Plain-language glosses. An explanation a clinician cannot read is not an explanation.
FEATURE_GLOSSES = {
    "theta_relative_power": "theta-band power relative to this patient's own baseline",
    "theta_alpha_ratio": "theta/alpha ratio, a common EEG marker in dementia research",
    "alpha_relative_power": "alpha-band power",
    "delta_relative_power": "delta-band power",
    "beta_relative_power": "beta-band power",
    "gamma_relative_power": "gamma-band power",
    "frontoparietal_coherence": "coordination between frontal and parietal regions",
    "spectral_entropy": "overall complexity of the EEG spectrum",
    "moca_total": "MoCA cognitive screening score",
    "moca_slope_12mo": "rate of change in MoCA score over 12 months",
    "gait_speed_ms": "walking speed",
    "gait_speed_deviation": "walking speed relative to this patient's own baseline",
    "rmssd_ms": "heart-rate variability (RMSSD)",
    "age_years": "age",
    "education_years": "years of education",
}


@dataclass
class Explanation:
    name: str
    contribution: float
    direction: str  # "increases-risk" | "decreases-risk"
    plain_language: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "contribution": round(self.contribution, 4),
            "direction": self.direction,
            "plain_language": self.plain_language,
        }


@dataclass
class RiskOutput:
    """A risk score that cannot exist without its reasoning."""

    score: float
    band: str
    top_features: list[Explanation]
    model_version: str = MODEL_VERSION
    window_months: int = 18
    max_subgroup_gap_at_release: Optional[float] = None
    brier_score: Optional[float] = None
    tier: Optional[int] = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if len(self.top_features) < MIN_EXPLANATION_FEATURES:
            raise ValueError(
                f"ADR-0006 violation: a risk score requires at least "
                f"{MIN_EXPLANATION_FEATURES} ranked contributing features, "
                f"got {len(self.top_features)}. There is no bypass path."
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "score": round(self.score, 4),
            "band": self.band,
            "window_months": self.window_months,
            "top_features": [f.to_dict() for f in self.top_features],
            "model_version": self.model_version,
            "max_subgroup_gap_at_release": self.max_subgroup_gap_at_release,
            "brier_score": self.brier_score,
            "tier": self.tier,
            "notes": self.notes,
        }

    def patient_facing_summary(self) -> str:
        """Plain-language version, per docs/02 §2.3 Q5.

        Deliberately says what the score does NOT mean. Developed jointly with a
        patient-and-family advisory council in a real deployment — nobody on that council is a
        data scientist, and that is the point of including them.
        """
        if self.band == "low":
            outlook = "we did not see signs that concern us right now"
        elif self.band == "moderate":
            outlook = "there are some signs we would like to keep a close eye on"
        else:
            outlook = "there are signs we would like to look at more closely with you"
        return (
            f"Based on your recent tests and recordings, {outlook} over the next "
            f"{self.window_months} months. This is not a diagnosis, and it does not mean you will "
            "definitely develop dementia. It means we would like to see you more often and talk "
            "about what support might help. You can ask us to explain any part of this, and you "
            "can ask us to stop using this tool at any time."
        )


def _band(score: float) -> str:
    if score < 0.33:
        return "low"
    if score < 0.66:
        return "moderate"
    return "elevated"


class RiskModel:
    """Soft-voting ensemble of a random forest and a gradient-boosting classifier."""

    def __init__(self, random_state: int = 42) -> None:
        self.feature_names: list[str] = []
        self.max_subgroup_gap_at_release: Optional[float] = None
        self.brier_score: Optional[float] = None
        self._fitted = False
        self.model = VotingClassifier(
            estimators=[
                (
                    "rf",
                    RandomForestClassifier(
                        n_estimators=300,
                        max_depth=8,
                        min_samples_leaf=5,
                        class_weight="balanced",
                        random_state=random_state,
                        n_jobs=-1,
                    ),
                ),
                (
                    "gb",
                    GradientBoostingClassifier(
                        n_estimators=200,
                        max_depth=3,
                        learning_rate=0.05,
                        random_state=random_state,
                    ),
                ),
            ],
            voting="soft",
        )

    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: Sequence[str]) -> RiskModel:
        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=int)
        if X.shape[1] != len(feature_names):
            raise ValueError("feature_names length must match X columns")
        self.feature_names = list(feature_names)
        self.model.fit(X, y)
        self._fitted = True
        return self

    def _importances(self) -> np.ndarray:
        """Average native feature importances across the ensemble members.

        Native importances, not post-hoc attribution — see ADR-0004 and ADR-0006 on why an
        inherently interpretable model is preferred over explaining a black box.
        """
        mats = [
            est.feature_importances_
            for _, est in zip(
                self.model.named_estimators_.keys(), self.model.named_estimators_.values()
            )
            if hasattr(est, "feature_importances_")
        ]
        if not mats:
            raise RuntimeError("no estimator exposes feature_importances_ (ADR-0004 requires it)")
        return np.mean(np.vstack(mats), axis=0)

    def predict(
        self,
        features: dict[str, Optional[float]],
        top_k: int = 5,
        tier_state: Optional[TierState] = None,
    ) -> RiskOutput:
        """Score one patient and attach ranked reasoning.

        Raises if the model was not fitted, or if any required feature is missing. Missing
        features are NOT imputed — docs/05 §5.7.

        TIER CEILING (ADR-0010). Conversion-risk scoring is a Tier 2 capability: it requires
        wristband physiology alongside ambient sensing, because the published performance of
        this model class at the MCI stage is weak enough that a thinner signal set cannot
        support the claim. Passing a ``tier_state`` below T2 raises ``ClaimCeilingViolation``.

        The tier is recorded on the output so that it travels with the score. A number that
        outlives the context justifying it is how a research prototype becomes a clinical
        incident.
        """
        if not self._fitted:
            raise RuntimeError("RiskModel.predict called before fit")

        if tier_state is not None:
            assert_claim_permitted(tier_state, Claim.CONVERSION_RISK)

        missing = [n for n in self.feature_names if features.get(n) is None]
        if missing:
            raise ValueError(
                "insufficient data: missing features "
                f"{missing}. Features are excluded, never imputed (docs/05 §5.7). "
                "The clinician surface must show 'insufficient data', not a score."
            )

        x = np.array([[float(features[n]) for n in self.feature_names]], dtype=float)
        score = float(self.model.predict_proba(x)[0, 1])

        imp = self._importances()
        # Direction: compare this patient's value to the training-set mean via the RF's view.
        order = np.argsort(imp)[::-1][: max(top_k, MIN_EXPLANATION_FEATURES)]
        explanations: list[Explanation] = []
        for i in order:
            name = self.feature_names[i]
            val = float(features[name])
            # Simple monotonic direction heuristic, honest about being a heuristic.
            increases = name in {
                "theta_relative_power",
                "theta_alpha_ratio",
                "delta_relative_power",
                "age_years",
            } or (name.endswith("_deviation") and val < 0)
            explanations.append(
                Explanation(
                    name=name,
                    contribution=float(imp[i]),
                    direction="increases-risk" if increases else "decreases-risk",
                    plain_language=FEATURE_GLOSSES.get(name, name.replace("_", " ")),
                )
            )

        return RiskOutput(
            score=score,
            tier=int(tier_state.tier) if tier_state else None,
            band=_band(score),
            top_features=explanations,
            max_subgroup_gap_at_release=self.max_subgroup_gap_at_release,
            brier_score=self.brier_score,
            notes=[
                "SYNTHETIC MODEL. Trained on data generated by dte.data.synthetic. "
                "Accuracy reflects the generator's assumptions, not biology.",
                "This is a RISK ESTIMATE, NOT A DIAGNOSIS.",
            ],
        )
