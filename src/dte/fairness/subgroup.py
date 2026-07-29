"""Subgroup fairness gate — the only gate with unconditional release-blocking authority.

Implements ``docs/07-validation-and-benchmarks.md`` §7.4 and
``docs/adr/0007-subgroup-fairness-gate.md``.

WHY THIS EXISTS
---------------
Models trained on largely Western datasets have been documented losing FIFTEEN TO TWENTY points of
accuracy on minority populations (docs/REFERENCES.md [14][19]). Accuracy has been observed falling
to around 70% in under-represented groups (docs/REFERENCES.md [19]).

Two things follow, and the second is the one usually missed:

1. Aggregate accuracy hides this completely. A model can report 88% overall while performing at
   70% for one group, and nothing on the dashboard says so.
2. **The gap does not close by itself as datasets grow.** It closes through deliberate rebalancing
   and explicit fairness constraints (docs/REFERENCES.md [13]). "We'll fix it when we have more
   data" has not historically worked.

THREE RULES THAT MAKE THIS REAL RATHER THAN DECORATIVE
------------------------------------------------------
1. It runs automatically in CI, not as a manual review step. A gate a human has to remember to run
   is a gate that gets skipped under deadline pressure — which is exactly when a biased model is
   most likely to ship.
2. **"Not enough data to certify" BLOCKS THE RELEASE TOO.** The alternative, shipping uncertified
   and assuming it is fine, is precisely how gaps reach production. If a subgroup cannot be
   certified, the documented intended population must be narrowed IN WRITING to exclude it, so the
   limitation is visible to every clinician who uses the tool.
3. Remediation is rebalancing and fairness constraints, never waiting for more data.

A NOTE ON THE 10-POINT THRESHOLD
--------------------------------
It is a judgement call, not a derived constant — defensible as roughly half the documented
15-20 point failure, but a choice. It is recorded as one (ADR-0007).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from dte.config import MAX_SUBGROUP_GAP, MIN_SUBGROUP_N


def _sensitivity(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    pos = y_true == 1
    return float(np.mean(y_pred[pos] == 1)) if pos.any() else None


def _false_positive_rate(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    neg = y_true == 0
    return float(np.mean(y_pred[neg] == 1)) if neg.any() else None


def _accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> Optional[float]:
    return float(np.mean(y_true == y_pred)) if y_true.size else None


@dataclass
class SubgroupMetrics:
    attribute: str
    group: str
    n: int
    accuracy: Optional[float] = None
    sensitivity: Optional[float] = None
    false_positive_rate: Optional[float] = None
    certifiable: bool = True
    reason: str = ""

    def to_dict(self) -> dict[str, object]:
        def r(v: Optional[float]) -> Optional[float]:
            return round(v, 4) if v is not None else None

        return {
            "attribute": self.attribute,
            "group": self.group,
            "n": self.n,
            "accuracy": r(self.accuracy),
            "sensitivity": r(self.sensitivity),
            "false_positive_rate": r(self.false_positive_rate),
            "certifiable": self.certifiable,
            "reason": self.reason,
        }


@dataclass
class FairnessReport:
    """The gate's verdict. ``passed=False`` blocks a release, unconditionally."""

    passed: bool
    max_gap: Optional[float]
    max_gap_group: Optional[str]
    population_accuracy: Optional[float]
    threshold: float = MAX_SUBGROUP_GAP
    min_subgroup_n: int = MIN_SUBGROUP_N
    subgroups: list[SubgroupMetrics] = field(default_factory=list)
    uncertifiable: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    remediation: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "max_gap": round(self.max_gap, 4) if self.max_gap is not None else None,
            "max_gap_group": self.max_gap_group,
            "population_accuracy": round(self.population_accuracy, 4)
            if self.population_accuracy is not None
            else None,
            "threshold": self.threshold,
            "min_subgroup_n": self.min_subgroup_n,
            "subgroups": [s.to_dict() for s in self.subgroups],
            "uncertifiable": self.uncertifiable,
            "blocking_reasons": self.blocking_reasons,
            "remediation": self.remediation,
        }

    def summary(self) -> str:
        verdict = "PASSED" if self.passed else "BLOCKED"
        gap = f"{self.max_gap:.1%}" if self.max_gap is not None else "n/a"
        return (
            f"Fairness gate {verdict}. max_gap={gap} (threshold {self.threshold:.0%}) "
            f"across {len(self.subgroups)} subgroups; {len(self.uncertifiable)} uncertifiable."
        )


def evaluate_fairness(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    attributes: dict[str, Sequence[str]],
    threshold: float = MAX_SUBGROUP_GAP,
    min_n: int = MIN_SUBGROUP_N,
) -> FairnessReport:
    """Run the gate.

    Args:
        y_true: ground-truth labels.
        y_pred: model predictions.
        attributes: mapping of attribute name to per-sample group labels. Expected keys in a real
            deployment: ``age_band``, ``sex``, ``race_ethnicity`` (where lawfully collected),
            ``primary_language``, ``education_band``, ``site``. These are used for EVALUATION
            ONLY and must never be model inputs.
        threshold: maximum permitted gap, as a proportion (0.10 = 10 percentage points).
        min_n: minimum samples for a subgroup to be certifiable.

    Returns:
        A :class:`FairnessReport`. ``passed=False`` means the release is blocked.
    """
    yt = np.asarray(y_true, dtype=int)
    yp = np.asarray(y_pred, dtype=int)
    if yt.shape != yp.shape:
        raise ValueError("y_true and y_pred must have the same shape")

    population_accuracy = _accuracy(yt, yp)

    subgroups: list[SubgroupMetrics] = []
    uncertifiable: list[str] = []
    gaps: list[tuple[float, str]] = []

    for attr, labels in attributes.items():
        lab = np.asarray(labels, dtype=object)
        if lab.shape[0] != yt.shape[0]:
            raise ValueError(f"attribute '{attr}' length does not match y_true")
        for group in sorted({str(g) for g in lab}):
            mask = lab.astype(str) == group
            n = int(mask.sum())
            m = SubgroupMetrics(attribute=attr, group=group, n=n)

            if n < min_n:
                m.certifiable = False
                m.reason = (
                    f"n={n} is below the minimum of {min_n}. CANNOT CERTIFY. "
                    "Collect more data, or narrow the documented intended population in writing "
                    "to exclude this group."
                )
                uncertifiable.append(f"{attr}={group} (n={n})")
                subgroups.append(m)
                continue

            m.accuracy = _accuracy(yt[mask], yp[mask])
            m.sensitivity = _sensitivity(yt[mask], yp[mask])
            m.false_positive_rate = _false_positive_rate(yt[mask], yp[mask])

            if m.accuracy is not None and population_accuracy is not None:
                gap = abs(m.accuracy - population_accuracy)
                gaps.append((gap, f"{attr}={group}"))
                m.reason = f"accuracy gap {gap:.1%} vs population {population_accuracy:.1%}"

            subgroups.append(m)

    max_gap, max_gap_group = max(gaps, key=lambda x: x[0]) if gaps else (None, None)

    blocking: list[str] = []
    remediation: list[str] = []

    if max_gap is not None and max_gap > threshold:
        blocking.append(
            f"Subgroup accuracy gap {max_gap:.1%} for {max_gap_group} exceeds the "
            f"{threshold:.0%} threshold."
        )
        remediation.append(
            "Rebalance the training data for the affected subgroup and add explicit fairness "
            "constraints. Do NOT wait for a larger dataset — the gap does not close on its own "
            "(docs/REFERENCES.md [13])."
        )

    if uncertifiable:
        blocking.append(
            f"{len(uncertifiable)} subgroup(s) cannot be certified: {', '.join(uncertifiable)}."
        )
        remediation.append(
            "Either collect enough data to certify these subgroups, or narrow the model's "
            "documented intended population IN WRITING so the limitation is visible to every "
            "clinician who uses the tool. Shipping uncertified is not an option."
        )

    return FairnessReport(
        passed=not blocking,
        max_gap=max_gap,
        max_gap_group=max_gap_group,
        population_accuracy=population_accuracy,
        threshold=threshold,
        min_subgroup_n=min_n,
        subgroups=subgroups,
        uncertifiable=uncertifiable,
        blocking_reasons=blocking,
        remediation=remediation,
    )
