"""Gait and mobility features from wearable IMU data.

Implements ``docs/03-digital-twin-engine.md`` §3.2.

These features feed requirement R2 (home monitoring). Note that a gait speed value is
meaningless in isolation: 0.94 m/s is unremarkable for one person and alarming for another. Only
comparison against the patient's OWN baseline makes it interpretable, which is why deviation
detection lives in ``dte.models.decline`` against ``TwinState.baseline`` rather than against any
population norm (principle P1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from dte.config import MIN_WALKING_BOUT_SECONDS

TRANSFORM_VERSION = "dte-signals-gait-0.1.0"


@dataclass
class GaitFeatures:
    gait_speed_ms: Optional[float] = None
    stride_time_cv: Optional[float] = None
    step_count_24h: Optional[int] = None
    sedentary_fraction: Optional[float] = None
    night_activity_index: Optional[float] = None
    longest_bout_s: float = 0.0
    movement_irregularity: float = 0.0
    quality: str = "absent"
    transform_version: str = TRANSFORM_VERSION

    @property
    def is_usable(self) -> bool:
        return self.quality == "sufficient"

    def as_flat_dict(self) -> dict[str, Optional[float]]:
        return {
            "gait_speed_ms": self.gait_speed_ms,
            "stride_time_cv": self.stride_time_cv,
            "step_count_24h": float(self.step_count_24h)
            if self.step_count_24h is not None
            else None,
            "sedentary_fraction": self.sedentary_fraction,
            "night_activity_index": self.night_activity_index,
        }


def extract_gait_features(
    stride_times_s: np.ndarray,
    stride_lengths_m: np.ndarray,
    bout_durations_s: np.ndarray,
    step_count_24h: Optional[int] = None,
    sedentary_fraction: Optional[float] = None,
    night_activity_index: Optional[float] = None,
) -> GaitFeatures:
    """Derive mobility features from detected walking bouts.

    Only bouts of at least ``MIN_WALKING_BOUT_SECONDS`` qualify for gait-speed computation.
    Short bouts — turning in a kitchen, standing up — produce speeds that are noise, and
    including them would make the personal baseline uselessly wide.
    """
    feats = GaitFeatures(
        step_count_24h=step_count_24h,
        sedentary_fraction=sedentary_fraction,
        night_activity_index=night_activity_index,
    )

    bouts = np.asarray(bout_durations_s, dtype=float)
    feats.longest_bout_s = float(bouts.max()) if bouts.size else 0.0

    st = np.asarray(stride_times_s, dtype=float)
    sl = np.asarray(stride_lengths_m, dtype=float)
    st = st[(st > 0.4) & (st < 3.0)]

    if feats.longest_bout_s < MIN_WALKING_BOUT_SECONDS or st.size < 5 or sl.size < 5:
        feats.quality = "insufficient" if st.size else "absent"
        return feats

    n = min(st.size, sl.size)
    feats.gait_speed_ms = float(np.mean(sl[:n] / st[:n]))
    feats.stride_time_cv = float(np.std(st, ddof=1) / np.mean(st))
    # Irregularity feeds the agitation index as independent movement evidence.
    feats.movement_irregularity = float(np.clip(feats.stride_time_cv / 0.20, 0.0, 1.0))
    feats.quality = "sufficient"
    return feats
