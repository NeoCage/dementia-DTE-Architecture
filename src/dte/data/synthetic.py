"""Synthetic data generator.

**This is the ONLY source of data in this repository.** No real patient data is present and none
may ever be added (``CONTRIBUTING.md``, ``DISCLAIMER.md``).

GENERATIVE ASSUMPTIONS — STATED SO THEY CAN BE CRITICISED
---------------------------------------------------------
Any model trained on this data learns these assumptions, not biology. They are listed explicitly
so that nobody mistakes a model's accuracy here for evidence about real patients:

1. **Theta elevation tracks conversion risk.** Converters are given higher theta relative power
   and a higher theta/alpha ratio. This is the assumption the architecture itself rests on and is
   its weakest link (docs/07 §7.6). Building it into the generator means a model trained here will
   "confirm" it — which is circular, and why the ablation study in docs/07 §7.6 matters.
2. **MoCA declines roughly linearly** over the observed window, with noise. Real trajectories are
   not linear.
3. **Gait speed declines with progression** and is drawn per-patient from an individual baseline.
4. **Subgroup structure is injected deliberately.** ``generate_cohort`` can under-represent a
   group AND make its signal noisier, so that the fairness gate has something real to catch. This
   is how the gate is tested.
5. **EEG is a sum of band-limited noise processes** plus artefacts. It is spectrally plausible and
   is NOT a biophysical simulation.
6. Sex, age and education effects are simple additive shifts.

If you extend this generator, document your assumptions here too.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from dte.config import BANDS, SAMPLING_RATE_HZ

FEATURE_NAMES = [
    "theta_relative_power",
    "alpha_relative_power",
    "delta_relative_power",
    "theta_alpha_ratio",
    "frontoparietal_coherence",
    "moca_total",
    "moca_slope_12mo",
    "gait_speed_ms",
    "rmssd_ms",
    "age_years",
    "education_years",
]


def generate_eeg(
    n_channels: int = 8,
    duration_s: float = 30.0,
    fs: float = SAMPLING_RATE_HZ,
    band_weights: Optional[dict[str, float]] = None,
    artefact_rate: float = 0.15,
    rng: Optional[np.random.Generator] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate a spectrally plausible synthetic EEG recording with artefacts.

    Returns:
        ``(raw_uv, motion_mask)`` where ``raw_uv`` is ``(n_channels, n_samples)`` in microvolts and
        ``motion_mask`` is a per-2-second-epoch boolean array simulating IMU-detected movement.

    The artefact rate defaults to 0.15, consistent with the documented 10-15% ambulatory signal
    quality loss (docs/REFERENCES.md [17]). This lets the artefact-rejection pipeline be exercised
    against a realistic contamination level rather than clean laboratory data.
    """
    rng = rng or np.random.default_rng()
    n = int(duration_s * fs)
    weights = band_weights or {"delta": 1.0, "theta": 1.0, "alpha": 1.2, "beta": 0.6, "gamma": 0.3}

    t = np.arange(n) / fs
    raw = np.zeros((n_channels, n))
    for ch in range(n_channels):
        sig = np.zeros(n)
        for band, (lo, hi) in BANDS.items():
            w = weights.get(band, 1.0)
            # Sum of random-phase sinusoids across the band approximates band-limited noise.
            for _ in range(12):
                f = rng.uniform(lo, hi)
                phase = rng.uniform(0, 2 * np.pi)
                sig += w * (10.0 / np.sqrt(f)) * np.sin(2 * np.pi * f * t + phase)
        sig += rng.normal(0, 2.0, n)  # sensor noise
        raw[ch] = sig

    # Inject artefacts on whole epochs, and mark a subset as IMU-detectable.
    epoch_len = int(2.0 * fs)
    n_epochs = n // epoch_len
    motion_mask = np.zeros(n_epochs, dtype=bool)
    n_bad = int(artefact_rate * n_epochs)
    if n_bad:
        bad = rng.choice(n_epochs, size=n_bad, replace=False)
        for e in bad:
            s, t0 = e * epoch_len, (e + 1) * epoch_len
            kind = rng.integers(0, 3)
            if kind == 0:  # movement — large amplitude, IMU sees it
                raw[:, s:t0] += rng.normal(0, 90.0, (n_channels, epoch_len))
                motion_mask[e] = True
            elif kind == 1:  # electrode pop — sharp gradient, IMU does not see it
                ch = rng.integers(0, n_channels)
                raw[ch, s:t0] += np.linspace(0, 250, epoch_len)
            else:  # disconnection — flatline
                ch = rng.integers(0, n_channels)
                raw[ch, s:t0] = rng.normal(0, 0.01, epoch_len)
    return raw, motion_mask


def generate_rr_intervals(
    duration_s: float = 300.0,
    mean_hr: float = 72.0,
    agitated: bool = False,
    rng: Optional[np.random.Generator] = None,
) -> np.ndarray:
    """Generate R-R intervals in milliseconds with a realistic frequency structure.

    ASSUMPTION 7: agitation is modelled as the classic autonomic signature — reduced overall
    variability (lower RMSSD) together with a shift of spectral power from the high-frequency
    (parasympathetic, ~0.25 Hz respiratory) band toward the low-frequency (~0.1 Hz) band, raising
    the LF/HF ratio.

    Explicit LF and HF oscillations are injected rather than relying on white noise, because a
    purely white-noise R-R series produces an LF/HF ratio fixed by the band widths alone — which
    would make the agitation index structurally unable to move. That would have hidden a real
    weakness behind a passing test.
    """
    rng = rng or np.random.default_rng()
    mean_rr = 60000.0 / (mean_hr + (20.0 if agitated else 0.0))
    n = max(int(duration_s / (mean_rr / 1000.0)), 60)

    if agitated:
        jitter_sd, lf_amp, hf_amp = 4.5, 11.0, 4.0
    else:
        jitter_sd, lf_amp, hf_amp = 13.0, 15.0, 21.0

    # Approximate elapsed time to place the oscillations in real frequency terms.
    t = np.arange(n) * (mean_rr / 1000.0)
    lf = lf_amp * np.sin(2 * np.pi * 0.10 * t + rng.uniform(0, 2 * np.pi))
    hf = hf_amp * np.sin(2 * np.pi * 0.25 * t + rng.uniform(0, 2 * np.pi))
    rr = mean_rr + lf + hf + rng.normal(0.0, jitter_sd, n)
    return np.clip(rr, 350, 1800)


@dataclass
class SyntheticPatient:
    patient_id: str
    age_years: float
    sex: str
    education_years: float
    race_ethnicity: str
    primary_language: str
    site: str
    converter: bool
    features: dict[str, float] = field(default_factory=dict)


@dataclass
class SyntheticCohort:
    patients: list[SyntheticPatient]
    feature_names: list[str]

    def to_arrays(self) -> tuple[np.ndarray, np.ndarray, dict[str, list[str]]]:
        """Return ``(X, y, attributes)`` ready for model fitting and the fairness gate."""
        X = np.array(
            [[p.features[n] for n in self.feature_names] for p in self.patients], dtype=float
        )
        y = np.array([int(p.converter) for p in self.patients], dtype=int)
        attributes = {
            "age_band": [
                "under-70" if p.age_years < 70 else ("70-79" if p.age_years < 80 else "80-plus")
                for p in self.patients
            ],
            "sex": [p.sex for p in self.patients],
            "race_ethnicity": [p.race_ethnicity for p in self.patients],
            "primary_language": [p.primary_language for p in self.patients],
            "education_band": [
                "under-12y" if p.education_years < 12 else "12y-plus" for p in self.patients
            ],
            "site": [p.site for p in self.patients],
        }
        return X, y, attributes


def generate_cohort(
    n: int = 400,
    conversion_rate: float = 0.35,
    underrepresented_fraction: float = 0.12,
    underrepresented_noise_multiplier: float = 2.5,
    seed: Optional[int] = 42,
) -> SyntheticCohort:
    """Generate a synthetic cohort with DELIBERATE subgroup structure.

    ``underrepresented_fraction`` and ``underrepresented_noise_multiplier`` together create a
    group that is both small and noisier — reproducing, in miniature, the pattern documented in
    the literature where accuracy falls on under-represented populations
    (docs/REFERENCES.md [14][19]). This exists so the fairness gate in
    :mod:`dte.fairness.subgroup` has something real to detect.

    Set ``underrepresented_noise_multiplier=1.0`` to generate a fair cohort and watch the gate pass.
    """
    rng = np.random.default_rng(seed)
    patients: list[SyntheticPatient] = []

    for i in range(n):
        converter = bool(rng.random() < conversion_rate)
        is_under = bool(rng.random() < underrepresented_fraction)
        noise = underrepresented_noise_multiplier if is_under else 1.0

        age = float(np.clip(rng.normal(74, 7), 55, 95))
        education = float(np.clip(rng.normal(12, 3.5), 2, 22))
        sex = "female" if rng.random() < 0.55 else "male"

        # ASSUMPTION 1: theta tracks conversion risk. See the module docstring on circularity.
        theta_base = 0.20 + (0.055 if converter else 0.0)
        theta = float(np.clip(rng.normal(theta_base, 0.022 * noise), 0.08, 0.42))
        alpha = float(
            np.clip(rng.normal(0.19 - (0.030 if converter else 0.0), 0.020 * noise), 0.05, 0.38)
        )
        delta = float(
            np.clip(rng.normal(0.27 + (0.020 if converter else 0.0), 0.028 * noise), 0.10, 0.45)
        )
        coherence = float(
            np.clip(rng.normal(0.47 - (0.075 if converter else 0.0), 0.055 * noise), 0.05, 0.95)
        )

        # ASSUMPTION 2: MoCA declines roughly linearly.
        moca = float(
            np.clip(rng.normal(24.5 - (2.6 if converter else 0.0), 2.1 * noise), 12, 30)
            + 0.10 * (education - 12)
        )
        moca_slope = float(rng.normal(-2.1 if converter else -0.45, 0.65 * noise))

        # ASSUMPTION 3: gait speed declines with progression.
        gait = float(
            np.clip(rng.normal(1.12 - (0.155 if converter else 0.0), 0.10 * noise), 0.35, 1.7)
        )
        rmssd = float(np.clip(rng.normal(30 - (4.5 if converter else 0.0), 8 * noise), 5, 80))

        patients.append(
            SyntheticPatient(
                patient_id=f"synthetic-{i:04d}",
                age_years=age,
                sex=sex,
                education_years=education,
                race_ethnicity="under-represented-group" if is_under else "majority-group",
                primary_language="other" if is_under and rng.random() < 0.6 else "english",
                site=f"site-{rng.integers(1, 4)}",
                converter=converter,
                features={
                    "theta_relative_power": theta,
                    "alpha_relative_power": alpha,
                    "delta_relative_power": delta,
                    "theta_alpha_ratio": theta / alpha if alpha > 0 else 1.0,
                    "frontoparietal_coherence": coherence,
                    "moca_total": moca,
                    "moca_slope_12mo": moca_slope,
                    "gait_speed_ms": gait,
                    "rmssd_ms": rmssd,
                    "age_years": age,
                    "education_years": education,
                },
            )
        )

    return SyntheticCohort(patients=patients, feature_names=list(FEATURE_NAMES))


@dataclass
class DayEvent:
    """One evaluation moment in a simulated day."""

    hour: int
    minute: int
    place_class: str
    place_significance: float
    agitated: bool
    eligible_content_count: int


def generate_day(
    seed: Optional[int] = None,
    n_events: int = 14,
) -> list[DayEvent]:
    """Generate a plausible day of evaluation moments for the MAP demo.

    Deliberately includes an evening event with high agitation, so that the agitation veto is
    exercised in the demo trace (see docs/04 §4.7).
    """
    rng = np.random.default_rng(seed)
    places = ["home", "known-routine", "known-significant", "novel"]
    weights = [0.45, 0.25, 0.18, 0.12]

    events: list[DayEvent] = []
    for _ in range(n_events):
        hour = int(rng.integers(7, 22))
        place = str(rng.choice(places, p=weights))
        sig = {
            "known-significant": float(rng.uniform(0.75, 0.95)),
            "home": 0.40,
            "known-routine": 0.30,
            "novel": 0.10,
        }[place]
        # Agitation becomes more likely in the evening — a real and well-described pattern.
        agitated = bool(rng.random() < (0.35 if hour >= 18 else 0.12))
        events.append(
            DayEvent(
                hour=hour,
                minute=int(rng.integers(0, 60)),
                place_class=place,
                place_significance=sig,
                agitated=agitated,
                eligible_content_count=int(rng.integers(0, 6)) if place != "novel" else 0,
            )
        )
    events.sort(key=lambda e: (e.hour, e.minute))
    return events
