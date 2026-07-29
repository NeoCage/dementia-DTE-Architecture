"""Configuration constants for the Digital Twin Engine.

Implements the thresholds documented in ``docs/07-validation-and-benchmarks.md``.

A note on why these are constants in code rather than tunable settings
---------------------------------------------------------------------
Some values here are *calibration parameters* and are expected to be tuned against real data
(``FUSION_WEIGHTS``, ``OPPORTUNITY_THRESHOLD``). Others are *safety invariants* that encode a
clinical judgement and must not be silently loosened (``REWARD_DISTRESS``, ``AGITATION_VETO``,
``MAX_SUBGROUP_GAP``, ``BASELINE_MIN_DAYS``). The second group is deliberately hard to change:
per ``CONTRIBUTING.md``, weakening one requires an Architecture Decision Record.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# --------------------------------------------------------------------------------------
# Signal quality gates — docs/05-data-architecture.md §5.7
# Below these thresholds a feature is marked insufficient and EXCLUDED from inference.
# It is never imputed. See the module docstring in dte.signals.eeg for why.
# --------------------------------------------------------------------------------------
MIN_USABLE_EPOCH_FRACTION = 0.60
MIN_VALID_CHANNELS = 6
MIN_BEAT_CONFIDENCE = 0.80
MIN_WALKING_BOUT_SECONDS = 30.0

# --------------------------------------------------------------------------------------
# EEG frequency bands (Hz) — docs/03-digital-twin-engine.md §3.2
# --------------------------------------------------------------------------------------
BANDS: dict[str, tuple[float, float]] = {
    "delta": (0.5, 4.0),
    "theta": (4.0, 8.0),
    "alpha": (8.0, 13.0),
    "beta": (13.0, 30.0),
    "gamma": (30.0, 45.0),
}
SAMPLING_RATE_HZ = 256.0

# --------------------------------------------------------------------------------------
# Memory Anchoring Pipeline — docs/04-memory-anchoring-pipeline.md
# --------------------------------------------------------------------------------------
# SAFETY INVARIANT. Agitation acts as a hard veto, not a weighted input: elevated agitation
# blocks a cue outright rather than lowering its confidence. §3.3.
AGITATION_VETO = 0.70

# CALIBRATION PARAMETERS. Starting points, not tuned values. §4.4.
FUSION_WEIGHTS: dict[str, float] = {"context": 0.35, "neural": 0.40, "content": 0.25}
OPPORTUNITY_THRESHOLD = 0.62

# SAFETY INVARIANTS — burden ceilings. §3.3.
REFRACTORY_MINUTES = 45
QUIET_HOURS = (22, 7)  # inclusive start hour, exclusive end hour, local time
DAILY_CUE_BUDGET = 8
CUE_LATENCY_TARGET_S = 2.0

# --------------------------------------------------------------------------------------
# Reward shaping — docs/04-memory-anchoring-pipeline.md §4.6, ADR-0008
#
# The asymmetry is the single most important set of numbers in the MAP. -2.0 against +1.0
# encodes the clinical judgement that upsetting someone is worse than failing to help them.
# A symmetric reward drifts the policy toward firing more often under a noisy signal.
# This one drifts toward silence. DO NOT "balance" these.
# --------------------------------------------------------------------------------------
REWARD_RECALLED = 1.0
REWARD_ENGAGED = 0.3
REWARD_IGNORED = 0.0
REWARD_DISTRESS = -2.0
DISTRESS_SUPPRESSION_HOURS = 24

# --------------------------------------------------------------------------------------
# Personal baseline — docs/03-digital-twin-engine.md §3.1
# SAFETY INVARIANT. No deviation alert may fire before the baseline is established.
# --------------------------------------------------------------------------------------
BASELINE_MIN_DAYS = 14
BASELINE_WINDOW_DAYS = 30
DEVIATION_Z_THRESHOLD = 2.0
DEVIATION_SUSTAINED_DAYS = 3
STALE_AFTER_HOURS = 72

# --------------------------------------------------------------------------------------
# Release gates — docs/07-validation-and-benchmarks.md §7.7
# SAFETY INVARIANTS. Each of these blocks a release.
# --------------------------------------------------------------------------------------
MIN_SENSITIVITY = 0.80  # B1.1
MAX_FALSE_POSITIVE_RATE = 0.20  # B1.2
MAX_SUBGROUP_GAP = 0.10  # B1.3 — ADR-0007
MIN_SUBGROUP_N = 30  # B1.3 — "cannot certify" also blocks
MAX_BRIER_SCORE = 0.18  # B1.4
MIN_EXPLANATION_FEATURES = 3  # B1.5 — ADR-0006
MAX_DISTRESS_RATE = 0.01  # B3.2 — the binding constraint on R3
DEVIATION_DETECTION_HOURS = 48  # B2.1


@dataclass(frozen=True)
class AlertBudgetConfig:
    """Alert ceiling — docs/03-digital-twin-engine.md §3.7.

    ``weekly_ceiling`` is a negotiated contract with the receiving clinical team, agreed in
    writing before launch. It is not a number the engineering team picks, and raising it
    requires the same conversation that set it.
    """

    weekly_ceiling: int = 11
    agreed_with: str = "nurse-navigator team (SYNTHETIC — illustrative)"
    agreed_on: str = "2026-01-15"

    def __post_init__(self) -> None:
        if self.weekly_ceiling < 1:
            raise ValueError("weekly_ceiling must be at least 1")


@dataclass(frozen=True)
class Config:
    """Top-level configuration bundle."""

    alert_budget: AlertBudgetConfig = field(default_factory=AlertBudgetConfig)
    opportunity_threshold: float = OPPORTUNITY_THRESHOLD
    agitation_veto: float = AGITATION_VETO
    daily_cue_budget: int = DAILY_CUE_BUDGET
    refractory_minutes: int = REFRACTORY_MINUTES

    def __post_init__(self) -> None:
        if not 0.0 < self.opportunity_threshold < 1.0:
            raise ValueError("opportunity_threshold must be in (0, 1)")
        if not 0.0 < self.agitation_veto <= 1.0:
            raise ValueError("agitation_veto must be in (0, 1]")


DEFAULT_CONFIG = Config()
