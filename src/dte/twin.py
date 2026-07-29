"""Twin State Store — the living, patient-specific model.

Implements ``docs/03-digital-twin-engine.md`` §3.1 and validates against
``schemas/json-schema/twin-state.schema.json``.

Design principle P1: the twin compares a person to THEMSELVES, not to a population. A gait speed
of 0.94 m/s is unremarkable for one person and alarming for another; only the personal baseline
makes it interpretable. That is what makes this object a twin rather than a dashboard.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from dte.config import (
    BASELINE_MIN_DAYS,
    BASELINE_WINDOW_DAYS,
    STALE_AFTER_HOURS,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RollingStat:
    """Rolling distributional statistics for one feature, for one patient."""

    mean: float = 0.0
    std: float = 0.0
    median: float = 0.0
    mad: float = 0.0  # median absolute deviation — used for robust z-scores
    n: int = 0
    window_days: int = BASELINE_WINDOW_DAYS
    _values: list[float] = field(default_factory=list, repr=False)

    def update(self, value: float) -> None:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return
        self._values.append(float(value))
        # Bound memory: keep the most recent window (assumes roughly daily observations).
        if len(self._values) > self.window_days * 24:
            self._values = self._values[-self.window_days * 24 :]
        vals = sorted(self._values)
        self.n = len(vals)
        self.mean = sum(vals) / self.n
        if self.n > 1:
            var = sum((v - self.mean) ** 2 for v in vals) / (self.n - 1)
            self.std = math.sqrt(var)
        self.median = (
            vals[self.n // 2] if self.n % 2 else (vals[self.n // 2 - 1] + vals[self.n // 2]) / 2
        )
        devs = sorted(abs(v - self.median) for v in vals)
        self.mad = (
            devs[self.n // 2] if self.n % 2 else (devs[self.n // 2 - 1] + devs[self.n // 2]) / 2
        )

    def z_score(self, value: float) -> Optional[float]:
        """Standard z-score. Returns None when the baseline cannot support one."""
        if self.n < 2 or self.std == 0:
            return None
        return (float(value) - self.mean) / self.std

    def robust_z(self, value: float) -> Optional[float]:
        """Median/MAD-based z-score. Preferred for deviation detection.

        Resistant to the outliers that ambulatory sensor data reliably produces: a single wild
        reading shifts the mean and inflates the standard deviation, but barely moves the median
        or the MAD.

        KNOWN LIMITATION: when the MAD is exactly zero — which happens when more than half the
        observations are identical, e.g. a sensor reporting a constant value — this falls back to
        the standard z-score and therefore loses its outlier resistance. That fallback is
        deliberate (returning None would disable deviation detection entirely), but it means a
        degenerate baseline offers no robustness advantage. Detecting a stuck sensor is a
        data-quality concern, handled by the quality gates in docs/05 §5.7, not here.
        """
        if self.n < 2:
            return None
        if self.mad == 0:
            return self.z_score(value)
        return 0.6745 * (float(value) - self.median) / self.mad


@dataclass
class Baseline:
    """Per-patient baseline. Never population-derived (principle P1)."""

    stats: dict[str, RollingStat] = field(default_factory=dict)
    n_observations: int = 0
    first_observed_at: Optional[datetime] = None
    established_at: Optional[datetime] = None
    window_days: int = BASELINE_WINDOW_DAYS

    @property
    def is_established(self) -> bool:
        """True once at least ``BASELINE_MIN_DAYS`` of observation exist.

        SAFETY INVARIANT: while this is False no deviation alert may fire. Alerting against an
        unestablished baseline is how monitoring pilots generate noise in week one and get
        abandoned in week six (docs/02 §2.4).
        """
        if self.first_observed_at is None:
            return False
        span = _utcnow() - self.first_observed_at
        return (
            span >= timedelta(days=BASELINE_MIN_DAYS) and self.n_observations >= BASELINE_MIN_DAYS
        )

    def update(self, features: dict[str, Optional[float]], at: Optional[datetime] = None) -> None:
        at = at or _utcnow()
        if self.first_observed_at is None:
            self.first_observed_at = at
        for name, value in features.items():
            if value is None:
                continue
            self.stats.setdefault(name, RollingStat(window_days=self.window_days)).update(value)
        self.n_observations += 1
        if self.is_established and self.established_at is None:
            self.established_at = at

    def deviation(
        self, feature: str, value: Optional[float], robust: bool = True
    ) -> Optional[float]:
        if value is None or feature not in self.stats:
            return None
        stat = self.stats[feature]
        return stat.robust_z(value) if robust else stat.z_score(value)


@dataclass
class ConsentSnapshot:
    """Per-modality consent — docs/08-security-and-privacy.md §8.5.

    Everything defaults to False. Consent is opt-in, never assumed.
    """

    neural_data: bool = False
    wearable_physiology: bool = False
    location_data: bool = False
    cue_delivery: bool = False
    family_visibility: bool = False
    federated_participation: bool = False
    research_use: bool = False
    last_confirmed: Optional[datetime] = None
    patient_stop_until: Optional[datetime] = None

    def permits_cue(self, now: Optional[datetime] = None) -> bool:
        """The patient stop-command overrides everything, including caregiver settings.

        A proxy can enrol a patient but cannot clear this flag
        (docs/08 §8.5, docs/10 §10.1).
        """
        now = now or _utcnow()
        if self.patient_stop_until and now < self.patient_stop_until:
            return False
        return self.cue_delivery


@dataclass
class Trajectory:
    """Projected cognitive trajectory with mandatory uncertainty."""

    horizon_months: float = 12.0
    metric: str = "moca_total"
    projected_values: list[float] = field(default_factory=list)
    ci_lower: list[float] = field(default_factory=list)
    ci_upper: list[float] = field(default_factory=list)
    confidence: float = 0.0
    point_estimate_suppressed: bool = False
    anchor_observations: list[str] = field(default_factory=list)


@dataclass
class ArmStats:
    value: float = 0.0
    n: int = 0
    suppressed_until: Optional[datetime] = None


@dataclass
class PolicyState:
    """Contextual bandit state. Learned per patient, never pooled (ADR-0008)."""

    arm_stats: dict[str, ArmStats] = field(default_factory=dict)
    total_pulls: int = 0
    epsilon: float = 0.10


@dataclass
class ProvenanceRecord:
    recorded_at: datetime
    source: str
    consent_basis: str
    device_id: Optional[str] = None
    transform_version: Optional[str] = None
    fields_written: list[str] = field(default_factory=list)


@dataclass
class TwinState:
    """One patient's Digital Twin.

    Not a 3-D brain rendering and not a biophysical simulation — a continuously updated
    statistical state object. See docs/03 §3.0 for why that distinction matters.
    """

    patient_id: str
    as_of: datetime = field(default_factory=_utcnow)
    neural: dict[str, Optional[float]] = field(default_factory=dict)
    physiology: dict[str, Optional[float]] = field(default_factory=dict)
    mobility: dict[str, Optional[float]] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    baseline: Baseline = field(default_factory=Baseline)
    trajectory: Optional[Trajectory] = None
    risk: Optional[dict[str, Any]] = None
    policy: PolicyState = field(default_factory=PolicyState)
    consent: ConsentSnapshot = field(default_factory=ConsentSnapshot)
    provenance: list[ProvenanceRecord] = field(default_factory=list)
    schema_version: str = "0.1.0"

    # ---------------------------------------------------------------- reads
    def is_stale(self) -> bool:
        """A twin with no recent data must SAY SO rather than silently serving old state."""
        return (_utcnow() - self.as_of) > timedelta(hours=STALE_AFTER_HOURS)

    def readable(self, modality: str) -> bool:
        """Consent gates READS, not merely UI visibility.

        If location consent is withdrawn, location features become unreadable — they are not
        just hidden on a dashboard (docs/03 §3.1).
        """
        return bool(getattr(self.consent, modality, False))

    def deviation(self, feature: str) -> Optional[float]:
        """Deviation of a current feature from this patient's own baseline."""
        for bucket in (self.neural, self.physiology, self.mobility):
            if feature in bucket:
                return self.baseline.deviation(feature, bucket[feature])
        return None

    def can_alert(self) -> bool:
        """SAFETY INVARIANT: no deviation alert before the baseline is established."""
        return self.baseline.is_established and not self.is_stale()

    # ---------------------------------------------------------------- writes
    def apply(
        self,
        *,
        neural: Optional[dict[str, Optional[float]]] = None,
        physiology: Optional[dict[str, Optional[float]]] = None,
        mobility: Optional[dict[str, Optional[float]]] = None,
        context: Optional[dict[str, Any]] = None,
        source: str = "unknown",
        consent_basis: str = "TREAT",
        device_id: Optional[str] = None,
        transform_version: Optional[str] = None,
        at: Optional[datetime] = None,
        update_baseline: bool = True,
    ) -> None:
        """Apply an update and append a provenance record.

        Every write is attributable. The provenance writer is not bypassable — this is what
        allows the system to answer "what did the twin look like when the clinician acted?"
        """
        at = at or _utcnow()
        written: list[str] = []

        if neural:
            self.neural.update(neural)
            written += [f"neural.{k}" for k in neural]
        if physiology:
            self.physiology.update(physiology)
            written += [f"physiology.{k}" for k in physiology]
        if mobility:
            self.mobility.update(mobility)
            written += [f"mobility.{k}" for k in mobility]
        if context:
            self.context.update(context)
            written += [f"context.{k}" for k in context]

        if update_baseline:
            merged: dict[str, Optional[float]] = {}
            merged.update(neural or {})
            merged.update(physiology or {})
            merged.update(mobility or {})
            if merged:
                self.baseline.update(merged, at=at)

        self.as_of = at
        self.provenance.append(
            ProvenanceRecord(
                recorded_at=at,
                source=source,
                consent_basis=consent_basis,
                device_id=device_id,
                transform_version=transform_version,
                fields_written=written,
            )
        )

    # ---------------------------------------------------------------- export
    def to_dict(self) -> dict[str, Any]:
        """Serialise to the shape defined by ``twin-state.schema.json``."""

        def enc(obj: Any) -> Any:
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, dict):
                return {k: enc(v) for k, v in obj.items() if not k.startswith("_")}
            if isinstance(obj, list):
                return [enc(v) for v in obj]
            return obj

        d = asdict(self)
        d["is_stale"] = self.is_stale()
        d["baseline"]["is_established"] = self.baseline.is_established
        return enc(d)
