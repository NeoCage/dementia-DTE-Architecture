# ADR-0008: Use a contextual bandit rather than full reinforcement learning for cue selection

- **Status:** Accepted
- **Date:** 2026-07-27
- **Deciders:** Model owner, clinical owner (OT/psychology), patient/family representative
- **Relates to:** R3 · [§3.6](../03-digital-twin-engine.md#36-personalisation-policy-service) · [§4](../04-memory-anchoring-pipeline.md)

## Context

Once the fusion service decides a cue *should* be delivered, something must choose *which* cue —
photograph, voice recording, ambient audio, or scent — and which specific item.

The textbook framing is sequential reinforcement learning: model the patient's cognitive state as an
environment, cues as actions, recall as reward, and learn an optimal policy (SARSA, Q-learning).

Three things make that a poor fit here:

1. **Episode count.** The daily cue budget is around eight. Sequential RL typically needs thousands of
   episodes to converge. At eight per day, that is years per patient.
2. **Exploration cost.** RL learns partly by taking suboptimal actions to see what happens. The
   suboptimal action here is delivering an inappropriate cue to a cognitively vulnerable person. That
   cost is not acceptable, and it is not adequately captured by a reward penalty.
3. **Auditability.** A clinician must be able to be shown why arm 3 was chosen. Explaining a learned
   Q-function is materially harder than explaining an arm value table.

There is also a modelling point: the sequential-credit-assignment problem RL solves may not exist here.
Whether a cue works depends mostly on the *current* context, not on a long chain of prior actions.

## Decision

**Cue selection is a contextual multi-armed bandit with ε-greedy exploration.**

- **Arms:** cue modalities, then specific content items within the chosen modality.
- **Context:** the fused feature vector (place semantics, time, neural state, physiology, history).
- **Reward:** observed patient response.
- **Learning is per-patient.** Cross-patient priors may initialise a new patient's arm values, but
  learned preferences are never pooled without federated aggregation and explicit consent.

**Reward shaping is deliberately asymmetric:**

| Outcome | Reward |
|---|---|
| Recalled | **+1.0** |
| Engaged, no recall | +0.3 |
| Ignored | 0.0 |
| **Distressed** | **−2.0** |

The −2.0 against +1.0 encodes a clinical judgement: **upsetting someone is worse than failing to help
them.** A policy learned with a symmetric reward drifts, under a noisy signal, toward firing more
often. This one drifts toward silence.

Unanswered caregiver confirmations are recorded as **missing**, never imputed as success. Imputing
missing feedback as positive is how a system learns to fire constantly.

## Consequences

### Positive
- Converges within the episode budget actually available.
- Auditable arm-by-arm: "photo has value 0.71 over 14 trials for this person, voice 0.66 over 9."
- Degrades gracefully — a poorly-estimated arm is a suboptimal choice, not a divergent policy.
- ε is tunable per phase: near-zero exploration during supervised Phase 4B, slightly higher later.
- Per-patient learning respects that what cues one person's memory is meaningless to another.

### Negative
- **Cannot learn sequential strategies** — e.g. that a scent cue works better if a photo cue preceded
  it that morning. If such effects turn out to be real and large, this decision is wrong.
- Per-patient learning means slow starts for new patients (mitigated by priors).
- ε-greedy is unsophisticated; Thompson sampling would likely be more efficient, but is harder to
  explain to a clinical committee.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Full RL (SARSA / Q-learning) | Needs episode counts we do not have and takes exploratory actions we cannot ethically permit on this population. |
| Fixed clinical rules, no learning | Safest and fully explainable, but forfeits the personalisation that is the entire point — personalised content outperforms generic (🔵 [25]). |
| Supervised model predicting best cue | Requires labelled "correct cue" data that does not exist and arguably cannot exist. |
| Thompson sampling | Likely better sample efficiency. Deferred: harder to explain, and explicability is doing real work in getting this approved at all. Worth revisiting. |

## How this is enforced

- [`../../src/dte/policy/cue_selector.py`](../../src/dte/policy/cue_selector.py).
- Reward asymmetry is a tested constant, not a tunable config value.

## Revisit if

Phase 4 data shows meaningful sequential effects between cues, **or** Thompson sampling can be
presented in a form a clinical committee will accept.
