"""Heart-rate variability features and the derived agitation index.

Implements ``docs/03-digital-twin-engine.md`` §3.2.

WHY THE AGITATION INDEX IS USED CONSERVATIVELY
----------------------------------------------
HRV is an imperfect proxy for agitation, and this module does not pretend otherwise. It is used
conservatively for exactly that reason: a false-positive agitation reading costs a missed cue,
while a false-negative costs a distressed person. The architecture treats "make it worse" as a
categorically different error from "miss an opportunity", so this index acts as a hard VETO on
cue delivery rather than as a weighted input (docs/03 §3.3, docs/04 §4.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.integrate import trapezoid

from dte.config import MIN_BEAT_CONFIDENCE

TRANSFORM_VERSION = "dte-signals-hrv-0.1.0"


@dataclass
class HRVFeatures:
    rmssd_ms: Optional[float] = None
    sdnn_ms: Optional[float] = None
    pnn50: Optional[float] = None
    lf_hf_ratio: Optional[float] = None
    resting_hr_bpm: Optional[float] = None
    agitation_index: Optional[float] = None
    beat_confidence: float = 0.0
    quality: str = "absent"
    transform_version: str = TRANSFORM_VERSION

    @property
    def is_usable(self) -> bool:
        return self.quality == "sufficient"

    def as_flat_dict(self) -> dict[str, Optional[float]]:
        return {
            "rmssd_ms": self.rmssd_ms,
            "sdnn_ms": self.sdnn_ms,
            "pnn50": self.pnn50,
            "lf_hf_ratio": self.lf_hf_ratio,
            "resting_hr_bpm": self.resting_hr_bpm,
            "agitation_index": self.agitation_index,
        }


def _agitation_index(
    rmssd: float,
    lf_hf: Optional[float],
    movement_irregularity: Optional[float] = None,
) -> float:
    """Map HRV and movement onto a bounded [0, 1] agitation estimate.

    Reduced RMSSD and elevated LF/HF both indicate sympathetic arousal. Movement irregularity from
    the IMU adds independent evidence. The mapping is intentionally simple and monotonic so that a
    clinician can be shown why the index moved — an opaque agitation model that vetoes cues would
    be the worst of both worlds.

    WHY WEIGHTS ARE RENORMALISED OVER AVAILABLE CHANNELS
    ---------------------------------------------------
    If a channel is unavailable (no IMU data, or LF/HF not computable from a short recording), the
    remaining weights are renormalised so the index still spans the full [0, 1] range.

    This is a safety property, not a cosmetic one. With fixed weights summing to 1.0 across three
    channels, a missing movement channel would cap the index at 0.80 — and a missing movement
    channel plus a missing LF/HF channel would cap it at 0.45, BELOW the 0.70 veto threshold. An
    absent input would then make the agitation veto unreachable, silently. A safety control must
    not be disarmed by missing data.

    Scaling reference points are typical adult values rather than this patient's own baseline. A
    production implementation should personalise them once a baseline exists — noted as a known
    simplification.
    """
    terms: list[tuple[float, float]] = []  # (weight, value)

    # Lower RMSSD indicates reduced parasympathetic tone. 45 ms is treated as fully calm.
    terms.append((0.45, float(np.clip(1.0 - (rmssd / 45.0), 0.0, 1.0))))

    if lf_hf is not None:
        # LF/HF of 1.0 is neutral; 4.0 and above is treated as fully aroused.
        terms.append((0.35, float(np.clip((lf_hf - 1.0) / 3.0, 0.0, 1.0))))

    if movement_irregularity is not None:
        terms.append((0.20, float(np.clip(movement_irregularity, 0.0, 1.0))))

    total_weight = sum(w for w, _ in terms)
    if total_weight <= 0:
        return 0.0
    return float(np.clip(sum(w * v for w, v in terms) / total_weight, 0.0, 1.0))


def extract_hrv_features(
    rr_intervals_ms: np.ndarray,
    beat_confidence: float = 1.0,
    movement_irregularity: Optional[float] = None,
) -> HRVFeatures:
    """Compute HRV features from a series of R-R intervals in milliseconds."""
    feats = HRVFeatures(beat_confidence=float(beat_confidence))

    rr = np.asarray(rr_intervals_ms, dtype=float)
    rr = rr[(rr > 300) & (rr < 2000)]  # physiologically plausible range

    if rr.size < 10 or beat_confidence < MIN_BEAT_CONFIDENCE:
        feats.quality = "insufficient" if rr.size else "absent"
        return feats

    diffs = np.diff(rr)
    feats.rmssd_ms = float(np.sqrt(np.mean(diffs**2)))
    feats.sdnn_ms = float(np.std(rr, ddof=1))
    feats.pnn50 = float(np.mean(np.abs(diffs) > 50.0))
    feats.resting_hr_bpm = float(60000.0 / np.mean(rr))

    # Frequency domain via Lomb-Scargle-free approximation: interpolate to even sampling.
    t = np.cumsum(rr) / 1000.0
    if t[-1] > 30.0:
        fs_i = 4.0
        ti = np.arange(t[0], t[-1], 1.0 / fs_i)
        rri = np.interp(ti, t, rr)
        rri = rri - rri.mean()
        freqs = np.fft.rfftfreq(rri.size, d=1.0 / fs_i)
        psd = np.abs(np.fft.rfft(rri)) ** 2
        lf = float(trapezoid(psd[(freqs >= 0.04) & (freqs < 0.15)]))
        hf = float(trapezoid(psd[(freqs >= 0.15) & (freqs < 0.40)]))
        feats.lf_hf_ratio = float(lf / hf) if hf > 0 else None

    feats.agitation_index = _agitation_index(
        rmssd=feats.rmssd_ms,
        lf_hf=feats.lf_hf_ratio,
        movement_irregularity=movement_irregularity,
    )
    feats.quality = "sufficient"
    return feats
