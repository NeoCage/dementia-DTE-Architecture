"""EEG artefact rejection and spectral feature extraction.

Implements ``docs/03-digital-twin-engine.md`` §3.2.

WHY ARTEFACT REJECTION IS A FIRST-CLASS COMPONENT, NOT A PREPROCESSING FOOTNOTE
------------------------------------------------------------------------------
Ambulatory EEG signal quality can fall 10-15% due to patient movement and electrode placement
(docs/REFERENCES.md [17]). A model validated on clean laboratory recordings and deployed against
ambulatory data has been validated against the wrong distribution. So artefact correction runs
BEFORE any inference, and the quality gate is enforced hard: below ``MIN_USABLE_EPOCH_FRACTION``
the system returns ``quality="insufficient"`` and the caller must NOT infer.

WHY WE NEVER IMPUTE
-------------------
Imputing missing physiological data in a monitoring system is how a confident-looking dashboard
ends up describing a patient who was not wearing the device. Insufficient means insufficient.

PRIVACY BOUNDARY (ADR-0002)
---------------------------
This module is the only place raw EEG exists. It accepts a raw array, returns derived features,
and the caller discards the raw array. There is no function here that persists or transmits raw
signal, and none may be added.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy import signal as sps
from scipy.integrate import trapezoid

from dte.config import (
    BANDS,
    MIN_USABLE_EPOCH_FRACTION,
    MIN_VALID_CHANNELS,
    SAMPLING_RATE_HZ,
)

TRANSFORM_VERSION = "dte-signals-eeg-0.1.0"


@dataclass
class EEGFeatures:
    """Derived EEG features. Contains no raw time-series, by design."""

    relative_power: dict[str, Optional[float]] = field(default_factory=dict)
    absolute_power: dict[str, Optional[float]] = field(default_factory=dict)
    theta_alpha_ratio: Optional[float] = None
    frontoparietal_coherence: Optional[float] = None
    spectral_entropy: Optional[float] = None
    usable_epoch_fraction: float = 0.0
    valid_channel_count: int = 0
    quality: str = "absent"
    transform_version: str = TRANSFORM_VERSION

    @property
    def is_usable(self) -> bool:
        return self.quality == "sufficient"

    def as_flat_dict(self) -> dict[str, Optional[float]]:
        """Flatten for twin ingestion and model input."""
        out: dict[str, Optional[float]] = {
            f"{band}_relative_power": self.relative_power.get(band) for band in BANDS
        }
        out["theta_alpha_ratio"] = self.theta_alpha_ratio
        out["frontoparietal_coherence"] = self.frontoparietal_coherence
        out["spectral_entropy"] = self.spectral_entropy
        out["usable_epoch_fraction"] = self.usable_epoch_fraction
        return out


def reject_artefacts(
    raw: np.ndarray,
    fs: float = SAMPLING_RATE_HZ,
    epoch_seconds: float = 2.0,
    amplitude_uv: float = 150.0,
    gradient_uv: float = 50.0,
    motion_mask: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, float, int]:
    """Multi-criterion artefact rejection.

    Four independent criteria, because no single one catches everything real headsets produce:

    1. **Amplitude** — epochs exceeding ``amplitude_uv`` are muscle or movement artefact.
    2. **Gradient** — large sample-to-sample jumps indicate electrode pop.
    3. **Flatline** — near-zero variance means a disconnected electrode, which is a *different*
       failure from noise and must be caught separately. Dead channels are identified BEFORE
       epoch-level criteria are applied, so one lost electrode does not invalidate the whole
       recording — see the inline note on why that ordering is load-bearing.
    4. **IMU gate** — the wristband accelerometer provides INDEPENDENT evidence of movement.
       This matters: excluding motion-contaminated epochs on independent evidence is far more
       reliable than guessing at motion from the EEG itself.

    Args:
        raw: ``(n_channels, n_samples)`` array in microvolts.
        motion_mask: optional per-epoch boolean array, True where the IMU indicates movement.

    Returns:
        ``(clean_epochs, usable_fraction, valid_channels)`` where ``clean_epochs`` has shape
        ``(n_kept_epochs, n_channels, epoch_len)``.
    """
    if raw.ndim != 2:
        raise ValueError(f"expected (n_channels, n_samples), got shape {raw.shape}")

    n_ch, n_s = raw.shape
    epoch_len = int(epoch_seconds * fs)
    if epoch_len <= 0 or n_s < epoch_len:
        return np.empty((0, n_ch, 0)), 0.0, 0

    n_epochs = n_s // epoch_len
    epochs = raw[:, : n_epochs * epoch_len].reshape(n_ch, n_epochs, epoch_len)
    epochs = np.transpose(epochs, (1, 0, 2))  # (n_epochs, n_channels, epoch_len)

    # STEP 1 — identify dead channels FIRST, across the whole recording.
    #
    # This ordering matters. A single disconnected electrode must not invalidate the entire
    # recording: it is one bad channel, not a bad session. Evaluating epoch-level criteria across
    # all channels first would let one flatlined electrode reject every epoch, and the pipeline
    # would report "no usable data" for a recording that is fine on 7 of 8 channels. Real headsets
    # lose electrodes routinely, so this is the common case, not an edge case.
    channel_alive = np.std(epochs, axis=(0, 2)) > 0.1
    valid_channels = int(channel_alive.sum())
    if valid_channels == 0:
        return np.empty((0, n_ch, 0)), 0.0, 0

    live = epochs[:, channel_alive, :]

    # STEP 2 — epoch-level criteria, evaluated only on channels that are alive.
    keep = np.ones(n_epochs, dtype=bool)
    keep &= np.max(np.abs(live), axis=(1, 2)) < amplitude_uv  # movement / muscle
    keep &= np.max(np.abs(np.diff(live, axis=2)), axis=(1, 2)) < gradient_uv  # electrode pop
    keep &= np.min(np.std(live, axis=2), axis=1) > 0.1  # transient dropout

    # STEP 3 — independent IMU evidence of movement.
    if motion_mask is not None:
        m = np.asarray(motion_mask, dtype=bool)
        if m.size >= n_epochs:
            keep &= ~m[:n_epochs]

    clean = epochs[keep]
    usable_fraction = float(keep.sum() / n_epochs)

    return clean, usable_fraction, valid_channels


def _band_powers(epochs: np.ndarray, fs: float) -> tuple[dict[str, float], np.ndarray, np.ndarray]:
    """Welch PSD averaged over epochs and channels, then integrated per band."""
    nperseg = min(int(fs * 2), epochs.shape[-1])
    freqs, psd = sps.welch(epochs, fs=fs, nperseg=nperseg, axis=-1)
    mean_psd = psd.mean(axis=(0, 1))  # average over epochs and channels
    powers: dict[str, float] = {}
    for band, (lo, hi) in BANDS.items():
        mask = (freqs >= lo) & (freqs < hi)
        powers[band] = float(trapezoid(mean_psd[mask], freqs[mask])) if mask.any() else 0.0
    return powers, freqs, psd


def _coherence(epochs: np.ndarray, fs: float, lo: float = 8.0, hi: float = 13.0) -> Optional[float]:
    """Mean magnitude-squared coherence between the first and last channel, alpha band.

    A crude stand-in for fronto-parietal connectivity: on a real montage the channel pair would
    be chosen from electrode positions, not by index. Documented rather than hidden.
    """
    if epochs.shape[1] < 2:
        return None
    a = epochs[:, 0, :].ravel()
    b = epochs[:, -1, :].ravel()
    nperseg = min(int(fs * 2), a.size)
    if nperseg < 8:
        return None
    freqs, cxy = sps.coherence(a, b, fs=fs, nperseg=nperseg)
    mask = (freqs >= lo) & (freqs < hi)
    return float(np.mean(cxy[mask])) if mask.any() else None


def extract_eeg_features(
    raw: np.ndarray,
    fs: float = SAMPLING_RATE_HZ,
    motion_mask: Optional[np.ndarray] = None,
) -> EEGFeatures:
    """Full edge pipeline: filter, reject artefacts, gate on quality, extract features.

    The quality gate comes BEFORE feature extraction is trusted. If it fails, the returned
    object has ``quality="insufficient"`` and ``is_usable == False``, and the caller must
    exclude it from inference rather than imputing it.
    """
    if raw.size == 0:
        return EEGFeatures(quality="absent")

    # Band-pass 0.5-45 Hz then notch mains interference.
    nyq = fs / 2.0
    b, a = sps.butter(4, [0.5 / nyq, min(45.0 / nyq, 0.99)], btype="band")
    filtered = sps.filtfilt(b, a, raw, axis=-1)
    for mains in (50.0, 60.0):
        if mains < nyq:
            bn, an = sps.iirnotch(mains, Q=30, fs=fs)
            filtered = sps.filtfilt(bn, an, filtered, axis=-1)

    clean, usable_fraction, valid_channels = reject_artefacts(
        filtered, fs=fs, motion_mask=motion_mask
    )

    feats = EEGFeatures(
        usable_epoch_fraction=usable_fraction,
        valid_channel_count=valid_channels,
    )

    # HARD QUALITY GATE — docs/05 §5.7. Never infer from junk.
    if (
        clean.shape[0] == 0
        or usable_fraction < MIN_USABLE_EPOCH_FRACTION
        or valid_channels < MIN_VALID_CHANNELS
    ):
        feats.quality = "insufficient"
        return feats

    powers, _, _ = _band_powers(clean, fs)
    total = sum(powers.values())
    feats.absolute_power = dict(powers)
    feats.relative_power = {k: (v / total if total > 0 else None) for k, v in powers.items()}

    alpha = powers.get("alpha", 0.0)
    feats.theta_alpha_ratio = float(powers["theta"] / alpha) if alpha > 0 else None
    feats.frontoparietal_coherence = _coherence(clean, fs)

    p = np.array([v for v in powers.values() if v > 0], dtype=float)
    if p.size:
        p = p / p.sum()
        feats.spectral_entropy = (
            float(-np.sum(p * np.log(p)) / np.log(p.size)) if p.size > 1 else 0.0
        )

    feats.quality = "sufficient"
    return feats
