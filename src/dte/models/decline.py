"""Cognitive trajectory forecasting and personal-baseline deviation detection.

Implements ``docs/03-digital-twin-engine.md`` §3.4 and ``docs/06-ml-architecture.md`` §6.4.

TWO DELIBERATE CHOICES WORTH READING
------------------------------------
1. **The trajectory forecaster never emits a point estimate without an interval, and suppresses
   the point estimate entirely when the interval is too wide to be actionable.** Presenting a
   confident-looking forecast built on two data points is how a forecasting tool loses clinical
   trust permanently.

2. **Deviation detection uses no machine learning at all** — a rolling robust z-score with CUSUM
   change detection. That is an architectural decision, not a shortfall (ADR-0004). A statistical
   method the nurse-navigator can understand and challenge beats a marginally better black box
   for this task, and it reduces the explainability burden, the drift surface and the compute
   footprint simultaneously.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from dte.config import (
    DEVIATION_SUSTAINED_DAYS,
    DEVIATION_Z_THRESHOLD,
)
from dte.twin import Baseline


@dataclass
class TrajectoryForecast:
    horizon_months: float
    metric: str
    projected_values: list[float] = field(default_factory=list)
    ci_lower: list[float] = field(default_factory=list)
    ci_upper: list[float] = field(default_factory=list)
    confidence: float = 0.0
    point_estimate_suppressed: bool = False
    n_anchors: int = 0
    note: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "horizon_months": self.horizon_months,
            "metric": self.metric,
            "projected_values": None
            if self.point_estimate_suppressed
            else [round(v, 2) for v in self.projected_values],
            "ci_lower": [round(v, 2) for v in self.ci_lower],
            "ci_upper": [round(v, 2) for v in self.ci_upper],
            "confidence": round(self.confidence, 3),
            "point_estimate_suppressed": self.point_estimate_suppressed,
            "n_anchors": self.n_anchors,
            "note": self.note,
        }


def forecast_trajectory(
    times_months: Sequence[float],
    values: Sequence[float],
    horizon_months: float = 12.0,
    metric: str = "moca_total",
    max_usable_ci_width: float = 8.0,
) -> TrajectoryForecast:
    """Fit a per-patient linear trend with a prediction interval.

    Args:
        times_months: observation times in months, relative to any origin.
        values: the cognitive measure at each time.
        max_usable_ci_width: if the interval at the horizon is wider than this, the point
            estimate is suppressed. For MoCA (0-30), 8 points is already close to useless.

    Returns:
        A forecast that is honest about its own uncertainty.
    """
    t = np.asarray(times_months, dtype=float)
    y = np.asarray(values, dtype=float)
    n = t.size

    if n < 2:
        return TrajectoryForecast(
            horizon_months=horizon_months,
            metric=metric,
            confidence=0.0,
            point_estimate_suppressed=True,
            n_anchors=n,
            note=(
                "Fewer than 2 observations. No forecast produced. At least 2 visits spanning "
                "6-12 months are required; a single snapshot underperforms a short longitudinal "
                "record (docs/REFERENCES.md [16])."
            ),
        )

    if n == 2:
        # A straight line fits two points EXACTLY, so the residual variance is zero and any
        # interval computed from it would be zero-width — the model would claim certainty it
        # cannot possibly have. With two observations the residual variance is not estimable at
        # all. Suppress the point estimate rather than emitting a confident-looking number.
        slope, intercept = np.polyfit(t, y, 1)
        future = np.arange(1.0, horizon_months + 1.0)
        t_future = t.max() + future
        projected = slope * t_future + intercept
        spread = max(abs(slope) * horizon_months, 2.0)
        return TrajectoryForecast(
            horizon_months=horizon_months,
            metric=metric,
            projected_values=[float(v) for v in projected],
            ci_lower=[float(v - spread) for v in projected],
            ci_upper=[float(v + spread) for v in projected],
            confidence=0.0,
            point_estimate_suppressed=True,
            n_anchors=2,
            note=(
                "Only 2 observations. A line fits two points exactly, so residual variance is not "
                "estimable and no honest confidence interval can be computed. Point estimate "
                "SUPPRESSED. At least 3 visits spanning 6-12 months are needed before a "
                "trajectory should be shown to a clinician (docs/REFERENCES.md [16])."
            ),
        )

    # Ordinary least squares on a single predictor.
    slope, intercept = np.polyfit(t, y, 1)
    fitted = slope * t + intercept
    dof = max(n - 2, 1)
    resid_se = float(np.sqrt(np.sum((y - fitted) ** 2) / dof))

    if resid_se == 0.0:
        # A perfect fit on more than two points is possible with synthetic data, and would
        # otherwise produce a zero-width interval. Refuse to imply certainty.
        resid_se = float(np.std(y, ddof=1)) or 1.0

    future = np.arange(1.0, horizon_months + 1.0)
    t_future = t.max() + future
    projected = slope * t_future + intercept

    t_mean = float(t.mean())
    sxx = float(np.sum((t - t_mean) ** 2)) or 1e-9
    # Prediction interval widens with distance from the observed range — as it should.
    se_pred = resid_se * np.sqrt(1.0 + 1.0 / n + (t_future - t_mean) ** 2 / sxx)
    tcrit = 1.96 if n > 30 else 2.78  # coarse; exact t would need scipy.stats
    lower = projected - tcrit * se_pred
    upper = projected + tcrit * se_pred

    ci_width_at_horizon = float(upper[-1] - lower[-1])
    suppress = ci_width_at_horizon > max_usable_ci_width
    confidence = float(np.clip(1.0 - ci_width_at_horizon / (2 * max_usable_ci_width), 0.0, 1.0))

    note = (
        f"Interval width at horizon is {ci_width_at_horizon:.1f}, above the usable limit of "
        f"{max_usable_ci_width:.1f}. Point estimate SUPPRESSED; report the range only. A "
        "confident-looking forecast the model cannot support does lasting damage to clinical trust."
        if suppress
        else f"Fitted on {n} observations. Slope {slope:+.2f} units/month."
    )

    return TrajectoryForecast(
        horizon_months=horizon_months,
        metric=metric,
        projected_values=[float(v) for v in projected],
        ci_lower=[float(v) for v in lower],
        ci_upper=[float(v) for v in upper],
        confidence=confidence,
        point_estimate_suppressed=suppress,
        n_anchors=n,
        note=note,
    )


@dataclass
class DeviationResult:
    feature: str
    deviated: bool
    robust_z: Optional[float]
    sustained_days: int
    change_point_index: Optional[int]
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "feature": self.feature,
            "deviated": self.deviated,
            "robust_z": round(self.robust_z, 3) if self.robust_z is not None else None,
            "sustained_days": self.sustained_days,
            "change_point_index": self.change_point_index,
            "detail": self.detail,
        }


class DeviationDetector:
    """Rolling robust z-score plus CUSUM change detection against a personal baseline.

    No machine learning. See the module docstring for why that is deliberate.
    """

    def __init__(
        self,
        z_threshold: float = DEVIATION_Z_THRESHOLD,
        sustained_days: int = DEVIATION_SUSTAINED_DAYS,
    ) -> None:
        self.z_threshold = z_threshold
        self.sustained_days = sustained_days

    @staticmethod
    def _cusum(values: np.ndarray, target: float, k: float, h: float) -> Optional[int]:
        """One-sided downward CUSUM. Returns the index where the change was detected."""
        s = 0.0
        for i, v in enumerate(values):
            s = max(0.0, s + (target - v) - k)
            if s > h:
                return i
        return None

    def evaluate(
        self,
        feature: str,
        recent_values: Sequence[float],
        baseline: Baseline,
    ) -> DeviationResult:
        """Assess whether a feature has deviated meaningfully from the personal baseline.

        SAFETY INVARIANT: returns ``deviated=False`` if the baseline is not yet established.
        Alerting against an unestablished baseline is how monitoring pilots generate noise in
        week one and get abandoned in week six.
        """
        if not baseline.is_established:
            return DeviationResult(
                feature=feature,
                deviated=False,
                robust_z=None,
                sustained_days=0,
                change_point_index=None,
                detail=(
                    f"Baseline not established ({baseline.n_observations} observations). "
                    "No deviation alert may fire before the minimum observation period."
                ),
            )

        stat = baseline.stats.get(feature)
        vals = np.asarray(recent_values, dtype=float)
        if stat is None or vals.size == 0:
            return DeviationResult(
                feature, False, None, 0, None, "no baseline statistic for feature"
            )

        zs = [baseline.deviation(feature, float(v), robust=True) for v in vals]
        zs_clean = [z for z in zs if z is not None]
        if not zs_clean:
            return DeviationResult(
                feature, False, None, 0, None, "baseline cannot support a z-score"
            )

        latest_z = zs_clean[-1]
        breaching = [abs(z) >= self.z_threshold for z in zs_clean]

        # Count the run of consecutive breaches ending at the most recent observation.
        sustained = 0
        for b in reversed(breaching):
            if b:
                sustained += 1
            else:
                break

        sigma = stat.mad / 0.6745 if stat.mad > 0 else stat.std
        cp = (
            self._cusum(vals, target=stat.median, k=0.5 * sigma, h=4.0 * sigma)
            if sigma > 0
            else None
        )

        deviated = sustained >= self.sustained_days
        detail = (
            f"{feature}={vals[-1]:.3f} vs personal median {stat.median:.3f} "
            f"(robust z={latest_z:+.2f}), sustained {sustained} consecutive observations "
            f"(threshold {self.sustained_days}). Baseline n={stat.n} over "
            f"{stat.window_days} days."
        )
        if cp is not None:
            detail += f" CUSUM change point at index {cp}."

        return DeviationResult(feature, deviated, latest_z, sustained, cp, detail)
