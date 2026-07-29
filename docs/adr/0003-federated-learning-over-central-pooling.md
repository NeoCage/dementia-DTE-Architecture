# ADR-0003: Use federated learning instead of centralised data pooling

- **Status:** Accepted (documented; **not implemented** in the reference code)
- **Date:** 2026-07-27
- **Deciders:** Data-governance officer, model owner, clinical informaticist
- **Relates to:** R1 · [§6.8](../06-ml-architecture.md#68-federated-learning) · Phase 5

## Context

Almost no single institution has enough dementia patients with adequate longitudinal follow-up to
train a robust model alone (🔵 [5]). Robustness across populations is not a nice-to-have here — models
trained on largely Western datasets have been documented losing 15–20 accuracy points on minority
populations (🔵 [14][19]), and the fairness gate ([ADR-0007](0007-subgroup-fairness-gate.md)) will
block release when that happens.

So we need more data, from more diverse sites. The conventional route is to pool it centrally.

Pooling creates a single repository of neural and cognitive data across multiple institutions. That is
a legal problem in many jurisdictions, an ethics-committee problem in most, and a security problem
everywhere — it is the highest-value target the system could possibly create.

## Decision

**Model improvement across institutions happens through federated learning. Raw or patient-level data
never leaves the institution that collected it.**

- Each site trains locally on its own data.
- Only model weight updates are shared, with differential-privacy noise applied.
- Updates are combined via secure aggregation, so the coordinator cannot inspect an individual site's
  contribution.
- The coordinator holds no patient data at any point.
- Federated participation is **separately consented** from clinical use.

**Implementation status must be stated plainly: this is documented, not built.** The reference code
contains no federated learning. An architecture diagram in a repository is frequently mistaken for
working software, and that mistake would be material here.

## Consequences

### Positive
- Access to population diversity without creating a central honeypot.
- Sites retain data sovereignty, which makes multi-site agreements achievable rather than theoretical.
- Aligns with GDPR data-minimisation and with jurisdictional data-residency requirements.
- Each institution can run the entire system standalone and join a federation later, or never.

### Negative
- Substantially more engineering complexity than pooling.
- Differential-privacy noise costs accuracy. The privacy/utility trade must be tuned and stated
  explicitly, not hidden.
- Debugging a model that trains across sites you cannot inspect is genuinely hard.
- Non-IID data across sites can destabilise convergence.
- **A patient's contribution cannot be un-learned after withdrawal** without full retraining. This is
  disclosed at consent rather than glossed over ([§5.4](../05-data-architecture.md#54-consent-gated-flows)).

### Accepted costs
- Phase 5 only. Not attempted before single-site validation succeeds.
- Requires ≥ 3 sites with materially different population profiles to be worth the complexity.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Centralised pooling under a data-sharing agreement | Simplest and most effective technically. Creates exactly the concentration of neural data that [ADR-0002](0002-edge-first-neural-processing.md) exists to avoid. Inconsistent to refuse cloud upload of raw EEG and then pool it across institutions. |
| Single-site only, no sharing | Viable and simple, but caps population diversity and therefore caps how well the fairness gate can ever be satisfied. |
| Synthetic data sharing | Promising, but synthetic EEG fidelity is not yet good enough to substitute for real training data. Worth revisiting. |
| Transfer learning from a published model | Useful for initialisation but inherits the source population's bias — the specific failure we are trying to avoid. |

## How this is enforced

- No patient-level export path exists from the feature store; research export is aggregate-only,
  k-anonymised and DP-noised.
- Federated participation is a distinct `Consent` provision, separately revocable.

## Revisit if

Synthetic EEG generation reaches fidelity sufficient for training, which would be simpler and safer
than federation.
