# ADR-0012: Caregiver outcomes are primary endpoints, and carer anxiety is a safety endpoint

- **Status:** Accepted
- **Date:** 2026-07-27
- **Deciders:** Clinical owner, patient/family representative, evaluation lead
- **Relates to:** R2, R3 · [§7](../07-validation-and-benchmarks.md) ·
  [ADR-0008](0008-contextual-bandit-for-cue-selection.md)

## Context

The benchmarks in §7 are patient- and clinician-facing: conversion sensitivity, false-positive
rate, deviation detection latency, alert volume, cue latency, distress rate. The caregiver appears
only as a recipient of alerts.

That is the wrong shape for this domain, on three independent grounds.

**The evidence base points at the caregiver.** The best-evidenced intervention in dementia care is
a counselling and support programme for *spouse caregivers*, which produced a 28.3% reduction in
the rate of nursing home placement and a model-predicted 557-day difference in median time to
placement — with improvements in caregiver social support, response to behaviour problems and
depressive symptoms accounting for 61.2% of that effect (Mittelman et al., 2006, *Neurology*
67(9):1592–1599). The mechanism runs through the caregiver.

**Caregiver state drives cost and utilisation.** Caregiver depression is associated with a 73%
increase in emergency department use among patients with dementia (adjusted IRR 1.73; Guterman et
al., 2019, *JAMA Neurology* 76(10):1166–1173). Collaborative care reducing caregiver burden on the
12-item Zarit and depression on the PHQ-9 produced a mean cost reduction of approximately $526 per
beneficiary per month (Possin et al., 2019; Guterman et al., 2023).

**The therapeutic premise of the MAP carries a specific carer risk.** The Cochrane review of
reminiscence therapy (🔵 LITERATURE: 22 studies, n=1,972; meta-analysis of 16, n=1,749) found small and
inconsistent benefits to quality of life, cognition and communication — and, on carer outcomes, no
evidence of benefit together with a **potential adverse outcome: carer anxiety at longer-term
follow-up**. The Memory Anchoring Pipeline inherits that risk profile. It is not acceptable to
build a cueing system on this evidence base without measuring the one harm the evidence base
actually flags.

## Decision

**Caregiver outcomes are promoted to primary endpoints, and carer anxiety becomes a release-gating
safety endpoint.**

Added to the §7 benchmark set:

| ID | Endpoint | Instrument | Gates release? |
|---|---|---|---|
| **B4.1** | Caregiver burden | Zarit Burden Interview (12-item) | ✅ |
| **B4.2** | Caregiver depressive symptoms | PHQ-9 | ✅ |
| **B4.3** | Time to institutionalisation | Days to first permanent placement | ✅ |
| **B4.4** | **Carer anxiety at long-term follow-up** | GAD-7 at ≥ 6 months | ✅ **as a safety endpoint** |

B4.4 is different in kind from the others. It is not a benefit to be maximised but a harm to be
excluded: a deterioration in carer anxiety at long-term follow-up **blocks release of the MAP**,
irrespective of how the patient-facing metrics perform. This mirrors the treatment of the subgroup
fairness gate in [ADR-0007](0007-subgroup-fairness-gate.md) — a control that can veto a release
rather than a number that gets weighed against others.

Informal care time is recorded as a descriptive measure (mean informal care time in Alzheimer's
disease has been reported at approximately 55.7 hours per week), but is not release-gating, because
it is self-reported and highly variable.

## Consequences

### Positive

- Aligns the evaluation with where the evidence says the mechanism actually runs.
- Aligns the evaluation with the payer, since caregiver burden and depression are the variables
  linked to utilisation and therefore to the cost reduction that funds deployment.
- Names, and measures, the one harm the reminiscence therapy literature actually reports, rather
  than inheriting the premise unexamined.
- Gives the T0 and T1 tiers something meaningful to be evaluated on. A twin with no sensing beyond
  caregiver report can still move B4.1 and B4.2.

### Negative

- Caregiver instruments require caregiver participation, which is burden in itself. The
  measurement schedule must be minimal, and it should be reviewed with a family advisory group
  before it is fixed.
- B4.4 requires long-term follow-up, which lengthens the path to release for the MAP specifically.
  This is the intended effect.
- A dyad with no identifiable primary caregiver cannot be evaluated on B4.1–B4.4. That population
  is real, frequently at highest risk, and this ADR does not solve for it.

### Neutral

- No change to the reward asymmetry in [ADR-0008](0008-contextual-bandit-for-cue-selection.md).
  Patient distress remains weighted −2.0 against +1.0 for successful recall. Carer anxiety operates
  at release-gate level rather than inside the policy's reward function, because it is measured
  over months and the policy operates over seconds.
