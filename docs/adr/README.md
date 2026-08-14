# Architecture Decision Records

An ADR records **why** a significant decision was made, what was rejected, and what it costs. It is
written once and never edited. If a decision is reversed, a new ADR supersedes the old one and the old
one stays in place.

The point is that a reader two years from now — or a reviewer, or you — can reconstruct the reasoning
without having been in the room.

## Index

| # | Decision | Status | Drives |
|---|---|---|---|
| [0001](0001-fhir-r5-canonical-model.md) | FHIR R5 as the canonical data model | Accepted | Interop tier |
| [0002](0002-edge-first-neural-processing.md) | Process neural data at the edge; raw EEG never leaves the device | Accepted | Privacy boundary |
| [0003](0003-federated-learning-over-central-pooling.md) | Federated learning instead of centralised data pooling | Accepted | Multi-site scale |
| [0004](0004-ensembles-over-deep-networks.md) | Tree ensembles instead of deep networks | Accepted | Model choice, footprint |
| [0005](0005-additive-not-replacement-workflow.md) | Additive workflow integration, never replacement | Accepted | Experience tier, governance |
| [0006](0006-explainability-as-a-hard-requirement.md) | Explainability is a release gate, not a feature | Accepted | Every clinician-facing output |
| [0007](0007-subgroup-fairness-gate.md) | A subgroup fairness gate with release-blocking authority | Accepted | CI, model registry |
| [0008](0008-contextual-bandit-for-cue-selection.md) | Contextual bandit instead of full reinforcement learning | Accepted | Memory Anchoring Pipeline |
| [0009](0009-no-biomarker-precondition.md) | No blood-biomarker precondition at intake | Accepted — **under review**, see [0011](0011-non-neural-core.md) | R1 data requirements |
| [0010](0010-tiered-fidelity-ladder.md) | A tiered fidelity ladder with enforced claim ceilings | Accepted | Every claim the twin makes |
| [0011](0011-non-neural-core.md) | Non-neural core; neural sensing as an optional tier | Accepted | Whole-system spine |
| [0012](0012-caregiver-outcomes-as-primary.md) | Caregiver outcomes primary; carer anxiety a safety endpoint | Accepted | §7 benchmarks, MAP release |

## Writing a new one

Copy [`0000-template.md`](0000-template.md), increment the number, and add a row above.
See [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md#architecture-decision-records).
| [ADR-0013](0013-biomarker-as-attribution-axis.md) | Biomarker status as an attribution axis, not a precondition | Accepted | Supersedes ADR-0009 |
