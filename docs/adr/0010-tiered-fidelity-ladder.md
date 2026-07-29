# ADR-0010: A tiered fidelity ladder with enforced claim ceilings

- **Status:** Accepted
- **Date:** 2026-07-27
- **Deciders:** Clinical owner, engineering lead, patient/family representative
- **Relates to:** R1, R2, R3 · [ADR-0011](0011-non-neural-core.md) · [§7](../07-validation-and-benchmarks.md)

## Context

The architecture as originally written assumed a single configuration: EEG headband, wristband,
phone, server. Every component was specified against that configuration, and the system had one
answer to the question "what can this twin claim?"

Real deployments do not look like that. The available sensing varies by site, by patient, by
funding, and — within a single patient — by the hour. A person takes the headband off. A wristband
runs flat. A community health worker in a low-resource setting has a phone and nothing else. The
original design had no vocabulary for any of this beyond "degraded", and no mechanism preventing a
degraded twin from continuing to assert what an intact one could.

That is a safety problem, not an engineering inconvenience. A conversion-risk score derived from a
caregiver questionnaire, presented in the same panel and the same format as one derived from twelve
weeks of multimodal sensing, is indistinguishable to the clinician reading it.

There is also an evidence problem, set out fully in [ADR-0011](0011-non-neural-core.md): the
published performance of neural sensing at the mild-cognitive-impairment stage is weak enough that
a design *requiring* it is placing its weight on its least-supported component.

## Decision

**Sensing fidelity is modelled explicitly as four ordered tiers, and every claim the twin makes is
gated on the tier it is currently operating at.**

| Tier | Sensing | Claim ceiling |
|---|---|---|
| **T0 — Report** | Caregiver and clinician report | Care-plan support, burden tracking. **No prediction.** |
| **T1 — Ambient** | + passive smartphone sensing | Deviation from personal baseline |
| **T2 — Physiological** | + wristband (HRV, actigraphy, IMU) | + MCI-to-dementia conversion risk |
| **T3 — Neural** | + EEG headband | + real-time memory-cue opportunity (MAP) |

Three properties make this real rather than descriptive:

1. **Tier is derived, never configured.** `dte.tiers.detect_tier()` computes it from live signal
   availability on every evaluation. A patient enrolled at T3 whose headband is off is a T2
   patient until it goes back on.
2. **Tiers are contiguous.** A headband with no phone and no wristband yields T0, not T3. Neural
   data without behavioural or physiological context is precisely what the MAP must not act on.
3. **The ceiling is enforced in code, with no bypass.** `assert_claim_permitted()` raises
   `ClaimCeilingViolation`. There is no `force=True`, and `tests/test_tiers.py` asserts that no
   such parameter exists.

### Two different failure modes, deliberately

- `RiskModel.predict` **raises** below T2. A risk score without the sensing to justify it means a
  clinician acting on a fiction.
- `OpportunityDetector.decide` **returns silent** below T3. A cue not delivered is a quiet
  afternoon, which is this pipeline's designed failure mode (P5). Degrading to a lower-quality cue
  would not be acceptable; degrading to silence is exactly right.

## Consequences

### Positive

- The weakest link in the architecture becomes a measured variable rather than an admission. §7.6
  asked whether the neural channel earns its cost; the ladder makes that question answerable
  per-tier, and pre-commits to accepting the answer if it is "no".
- A deployable base configuration now exists. T1 requires a phone and a caregiver, which is
  reachable in the settings where 71% of people with dementia will live by 2050.
- Claims travel with their provenance. `RiskOutput.tier` and `OpportunityDecision.tier` are
  serialised, so a score cannot outlive the context that justified it.
- Alignment with reimbursement becomes tractable, because each tier can be costed and matched
  against a payment mechanism separately (see Chapter 4).

### Negative

- **More states to test.** Four tiers times four claims is a larger surface than one configuration,
  and the interaction with the fairness gate needs care: subgroup certification must hold *at each
  tier*, not just in aggregate. This is not yet implemented and is the most likely source of a
  future correctness bug.
- **Callers must supply a `TierState`.** It is optional in the current signatures for backward
  compatibility, which means a caller that omits it silently skips enforcement. That default is
  wrong and should be inverted before any deployment; it is retained now only to avoid breaking
  the existing demo surface.
- Documentation and code can drift apart. The tier table above and `MINIMUM_TIER_FOR_CLAIM` in
  `dte/tiers.py` must be changed together.

### Neutral

- The tier vocabulary is specific to this system. It is not a standard, and no claim is made that
  T2 here means what T2 might mean elsewhere.

## What would make us reverse this

If prospective evaluation showed that a T1 configuration achieves conversion-risk performance
statistically indistinguishable from T2, the ceiling for `CONVERSION_RISK` should drop to T1 and
the wristband becomes optional too. The ladder is a hypothesis about where value sits, and it is
meant to be revised by evidence rather than defended.
