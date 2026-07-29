"""Contextual bandit cue selection.

Implements ``docs/03-digital-twin-engine.md`` §3.6, ``docs/04-memory-anchoring-pipeline.md`` §4.6
and ``docs/adr/0008-contextual-bandit-for-cue-selection.md``.

WHY A BANDIT AND NOT FULL REINFORCEMENT LEARNING
------------------------------------------------
Three reasons, all decisive (ADR-0008):

1. **Episode count.** The daily cue budget is about eight. Sequential RL typically needs
   thousands of episodes. At eight per day that is years per patient.
2. **Exploration cost.** RL learns partly by taking suboptimal actions. The suboptimal action
   here is delivering an inappropriate cue to a cognitively vulnerable person. That cost is not
   acceptable and is not adequately captured by a reward penalty.
3. **Auditability.** A clinician must be able to be shown why arm 3 was chosen. An arm-value
   table can be shown. A learned Q-function cannot, not usefully.

THE REWARD ASYMMETRY IS THE POINT
---------------------------------
distress = -2.0 against recalled = +1.0 encodes a clinical judgement: upsetting someone is worse
than failing to help them. A policy learned with a symmetric reward drifts, under a noisy signal,
toward firing more often. This one drifts toward silence. These constants live in
``dte.config`` as safety invariants and must not be "balanced".
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from dte.config import (
    DISTRESS_SUPPRESSION_HOURS,
    REWARD_DISTRESS,
    REWARD_ENGAGED,
    REWARD_IGNORED,
    REWARD_RECALLED,
)


class CueArm(str, Enum):
    """Cue modalities. See docs/04 §4.5 for the constraints on each."""

    PHOTO = "photo"
    VOICE = "voice"
    AMBIENT_AUDIO = "ambient-audio"
    SCENT = "scent"


class Response(str, Enum):
    RECALLED = "recalled"
    ENGAGED = "engaged-no-confirmed-recall"
    IGNORED = "ignored"
    DISTRESSED = "distressed"
    UNKNOWN = "unknown"  # caregiver confirmation not yet given


def reward_for(response: Response) -> Optional[float]:
    """Map an observed response to a reward.

    ``UNKNOWN`` returns None — recorded as MISSING, never imputed as success. Systems that impute
    missing feedback as positive learn to fire constantly (docs/04 §4.6).
    """
    return {
        Response.RECALLED: REWARD_RECALLED,
        Response.ENGAGED: REWARD_ENGAGED,
        Response.IGNORED: REWARD_IGNORED,
        Response.DISTRESSED: REWARD_DISTRESS,
        Response.UNKNOWN: None,
    }[response]


@dataclass
class _ArmState:
    value: float = 0.0
    n: int = 0
    suppressed_until: Optional[datetime] = None

    def available(self, now: datetime) -> bool:
        return self.suppressed_until is None or now >= self.suppressed_until


@dataclass
class Selection:
    arm: CueArm
    exploratory: bool
    arm_value: float
    arm_n: int
    context_key: str
    alternatives: dict[str, tuple[float, int]] = field(default_factory=dict)

    def explain(self) -> str:
        alts = " | ".join(f"{k} {v:.2f} n={n}" for k, (v, n) in sorted(self.alternatives.items()))
        mode = "exploratory" if self.exploratory else "exploitative"
        return (
            f"arm={self.arm.value} (value {self.arm_value:.2f}, n={self.arm_n}, {mode}) "
            f"context={self.context_key} | alternatives: {alts}"
        )


class CueSelector:
    """Per-patient epsilon-greedy contextual bandit over cue modalities.

    Learning is PER PATIENT. Cross-patient priors may initialise a new patient's arm values, but
    learned preferences are never pooled without federated aggregation and explicit consent
    (ADR-0003, ADR-0008). What cues one person's memory is meaningless to another.
    """

    def __init__(
        self,
        epsilon: float = 0.10,
        arms: Optional[list[CueArm]] = None,
        priors: Optional[dict[CueArm, float]] = None,
        seed: Optional[int] = None,
    ) -> None:
        self.epsilon = epsilon
        self.arms = arms or list(CueArm)
        self._rng = random.Random(seed)
        self._state: dict[str, dict[CueArm, _ArmState]] = {}
        self._priors = priors or {}
        self.total_pulls = 0

    @staticmethod
    def context_key(place_class: str, hour_of_day: int) -> str:
        """Coarse context discretisation.

        Deliberately coarse: fine-grained contexts would each collect too few observations to
        estimate an arm value from, given a budget of ~8 cues/day.
        """
        if hour_of_day < 12:
            slot = "morning"
        elif hour_of_day < 17:
            slot = "afternoon"
        else:
            slot = "evening"
        return f"{place_class}|{slot}"

    def _arms_for(self, key: str) -> dict[CueArm, _ArmState]:
        if key not in self._state:
            self._state[key] = {
                a: _ArmState(value=self._priors.get(a, 0.0), n=0) for a in self.arms
            }
        return self._state[key]

    def select(
        self,
        place_class: str,
        hour_of_day: int,
        available_arms: Optional[list[CueArm]] = None,
        now: Optional[datetime] = None,
    ) -> Optional[Selection]:
        """Choose an arm. Returns None when no arm is available."""
        now = now or datetime.now(timezone.utc)
        key = self.context_key(place_class, hour_of_day)
        states = self._arms_for(key)

        candidates = [
            a for a in (available_arms or self.arms) if a in states and states[a].available(now)
        ]
        if not candidates:
            return None

        exploratory = self._rng.random() < self.epsilon
        if exploratory:
            arm = self._rng.choice(candidates)
        else:
            # Tie-break toward the arm with more observations — prefer the better-known option.
            arm = max(candidates, key=lambda a: (states[a].value, states[a].n))

        self.total_pulls += 1
        return Selection(
            arm=arm,
            exploratory=exploratory,
            arm_value=states[arm].value,
            arm_n=states[arm].n,
            context_key=key,
            alternatives={a.value: (states[a].value, states[a].n) for a in candidates},
        )

    def update(
        self,
        selection: Selection,
        response: Response,
        now: Optional[datetime] = None,
    ) -> Optional[float]:
        """Update the arm value from an observed response.

        A distress response additionally suppresses that modality for
        ``DISTRESS_SUPPRESSION_HOURS``. The system retreats rather than retrying.
        """
        now = now or datetime.now(timezone.utc)
        reward = reward_for(response)
        states = self._arms_for(selection.context_key)
        st = states[selection.arm]

        if response is Response.DISTRESSED:
            st.suppressed_until = now + timedelta(hours=DISTRESS_SUPPRESSION_HOURS)

        if reward is None:
            # Missing feedback. Not imputed, not counted.
            return None

        st.n += 1
        st.value += (reward - st.value) / st.n  # incremental sample mean
        return reward

    def snapshot(self) -> dict[str, dict[str, dict[str, float]]]:
        """Auditable view of everything the policy has learned for this patient."""
        return {
            key: {arm.value: {"value": round(s.value, 4), "n": s.n} for arm, s in arms.items()}
            for key, arms in self._state.items()
        }
