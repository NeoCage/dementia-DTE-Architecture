# ADR-0004: Use tree ensembles rather than deep neural networks

- **Status:** Accepted
- **Date:** 2026-07-27
- **Deciders:** Model owner, clinical owner, lead engineer
- **Relates to:** R1, R2 · [§6.4](../06-ml-architecture.md#64-stage-3--model-selection) · Principles P3, P9

## Context

Deep learning is the default assumption for EEG work, and end-to-end deep models can outperform
feature-based approaches given enough labelled data and compute.

We have neither, and two other criteria outrank raw accuracy here.

**Interpretability.** A clinician who cannot see why a model reached its conclusion will not act on it.
Explainable approaches have repeatedly improved clinician trust in exactly this setting (🔵 [18]), and
clinician resistance to this class of tool is a trust problem rather than a literacy problem
([§10.5](../10-governance-and-ethics.md#105-anticipated-resistance-and-what-it-actually-means)).

**Computational footprint.** A model that needs a GPU cluster is simply not an option for a lot of
community health systems. Since the population that most needs this technology is concentrated where
resources are thinnest, a GPU requirement is not a technical constraint — it is an equity one.

Meanwhile the evidence for ensembles is good: random forests and gradient-boosted trees combined have
reached close to **88%** accuracy in multimodal dementia risk stratification (🔵 [4]), and no single
algorithm wins every dementia-prediction task.

## Decision

**Tree ensembles (random forest + gradient-boosted trees, soft-voted) for risk stratification. No deep
neural networks in the v1 architecture.**

Related choices in the same spirit:
- Cognitive trajectory: per-patient linear mixed-effects / robust regression with explicit confidence
  intervals.
- **Baseline deviation: rolling robust z-score with CUSUM change detection — no machine learning at
  all.** Using statistics where statistics suffice is a deliberate architectural decision, not a
  shortfall. It reduces the explainability burden, the drift surface and the compute footprint
  simultaneously.

Target deployment envelope: **4 vCPU, 16 GB RAM, no GPU.**

## Consequences

### Positive
- Native feature importances give explainability essentially for free, satisfying
  [ADR-0006](0006-explainability-as-a-hard-requirement.md) without a separate post-hoc method.
- Trains on hundreds of patients rather than tens of thousands.
- Runs on a modest on-premise server, which is what makes the deployment topology in
  [§9.2](../09-deployment-architecture.md#92-topology) possible.
- Robust to the mixed tabular feature types we actually have.
- Fast to retrain, which matters for drift response.

### Negative
- **We are probably leaving accuracy on the table** for the raw-signal task. An end-to-end deep model
  with sufficient data would likely outperform this. Accepted knowingly.
- Requires good hand-engineered features, which means a neurologist and an ML engineer must actually
  collaborate rather than throwing raw signal at a network.
- Does not exploit temporal structure within an EEG epoch the way a recurrent or transformer model
  could.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| End-to-end deep learning on raw EEG | Best ceiling accuracy. Needs data volume we do not have, compute many target sites do not have, and produces explanations clinicians have told this field repeatedly they do not trust. |
| CNN on spectrograms | Middle ground, still GPU-preferred and still weaker on interpretability than feature importances. |
| Logistic regression only | Maximally interpretable but likely underfits genuinely multimodal, non-linear interactions. |
| Deep model + post-hoc SHAP | Post-hoc explanation of a black box is not the same as an interpretable model, and the distinction matters when a clinician wants to *challenge* a score, not just be told a reason. |

## How this is enforced

- CI runs the test suite on CPU only. A GPU dependency would fail the build.
- Model registry requires native feature importances; a model that cannot supply them cannot be
  promoted.

## Revisit if

A site accumulates enough labelled longitudinal data that a deep model's accuracy advantage exceeds
the interpretability cost — **and** an interpretable surrogate can be validated alongside it.
