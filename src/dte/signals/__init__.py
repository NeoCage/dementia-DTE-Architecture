"""Edge-tier signal processing. Implements docs/03-digital-twin-engine.md §3.2."""

from dte.signals.eeg import EEGFeatures, extract_eeg_features, reject_artefacts
from dte.signals.gait import GaitFeatures, extract_gait_features
from dte.signals.hrv import HRVFeatures, extract_hrv_features

__all__ = [
    "EEGFeatures",
    "extract_eeg_features",
    "reject_artefacts",
    "HRVFeatures",
    "extract_hrv_features",
    "GaitFeatures",
    "extract_gait_features",
]
