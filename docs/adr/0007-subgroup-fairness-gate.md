# ADR-0007: Enforce a subgroup fairness gate with release-blocking authority

- **Status:** Accepted
- **Date:** 2026-07-27
- **Deciders:** Model owner, clinical owner, data-governance officer, patient/family representative
- **Relates to:** R1, R2, R3 · [§7.4](../07-validation-and-benchmarks.md#74-the-subgroup-fairness-gate) · Principle P4

## Context

Models trained on largely Western datasets have been documented losing **fifteen to twenty points** of
accuracy on minority populations (🔵 [14][19]). Accuracy has been observed falling to around **70%** in
under-represented groups when training data does not reflect them (🔵 [19]).

Two things follow, and the second is the one usually missed.

First, aggregate accuracy hides this completely. A model can report 88% overall while performing at
70% for one group, and nothing on the dashboard says so.

Second, **the gap does not close by itself as datasets grow.** It closes through deliberate
rebalancing and explicit fairness constraints (🔵 [13]). "We'll fix it when we have more data" has not
historically worked.

A benchmark that does not check for the gap will not catch it before deployment. And a check that
depends on someone remembering to run it will be skipped under deadline pressure — which is when
shortcuts get taken and when a biased model is most likely to ship.

## Decision

**A subgroup fairness gate runs automatically in CI on every model build and has unconditional
authority to block a release.**

- Evaluation is stratified by age band, sex, race/ethnicity (where lawfully collected), primary
  language, an education proxy, and site/geography.
- Per-subgroup sensitivity, false-positive rate, calibration and AUC are computed.
- **`max_gap ≤ 10 percentage points`** between any subgroup and the population average, on every
  metric.
- **`n ≥ 30` per subgroup**, or the gate fails.
- `max_gap` at release is recorded permanently in the model registry.

Three rules make it real rather than decorative:

1. **It runs automatically, not as a manual review step.**
2. **"Not enough data to certify" blocks the release too.** The alternative — shipping uncertified and
   assuming it is fine — is precisely how gaps reach production. If a subgroup cannot be certified, the
   *documented intended population* must be narrowed in writing to exclude it, so the limitation is
   visible to every clinician who uses the tool.
3. **Remediation is rebalancing and explicit fairness constraints**, not waiting for more data.

## Consequences

### Positive
- Makes an invisible failure mode visible and blocking.
- Rule 2 converts a data gap into an honest scope limitation rather than a silent risk.
- Recording `max_gap` in the registry means the number is auditable years later.
- Supports EU AI Act high-risk obligations around accuracy and non-discrimination.

### Negative
- **Will block releases.** That is the intent, and it will be unpopular during a delivery crunch.
- Requires collecting demographic attributes, which has its own privacy tension — mitigated by
  collecting them for evaluation only, never as model inputs.
- Some jurisdictions restrict collecting race/ethnicity; proxies are weaker.
- The `n ≥ 30` requirement makes small-site deployment harder, and pushes toward
  [ADR-0003](0003-federated-learning-over-central-pooling.md).

### Accepted costs
- 10 points is a judgement call, not a derived constant. It is defensible as roughly half the
  choice, and it is recorded as one. An earlier draft justified it by appeal to a specific documented percentage loss; that citation could not be verified and has been removed, which does not weaken the argument for having a gate.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Report subgroup metrics without blocking | Reporting without authority is documentation, not a control. Reported-and-ignored is the normal outcome. |
| Manual fairness review before release | Depends on someone remembering, under exactly the pressure that makes people forget. |
| Equalised odds as a formal constraint | Mathematically cleaner, harder for a clinical committee to interpret and act on. A simple, explicable gap threshold gets enforced; an elegant one gets waived. |
| Ship with a warning label | Puts the burden on the clinician to remember which patients the model is worse for, mid-consultation. |

## How this is enforced

- [`../../src/dte/fairness/subgroup.py`](../../src/dte/fairness/subgroup.py), tested in
  [`../../tests/test_fairness.py`](../../tests/test_fairness.py).
- CI job fails the build on gate failure.
- Model registry rejects promotion without a recorded `max_gap`.

## Revisit if

The 10-point threshold proves either unachievable across the board (suggesting a data problem needing
a different response) or trivially achievable everywhere (suggesting it is too loose).
