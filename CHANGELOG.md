# Changelog

## [Unreleased] - 2026-07-30

### Added
- **ADR-0013: biomarker status as an attribution axis.** A second dimension, orthogonal to the
  sensing tier, governing what the twin may say about the *cause* of a deviation rather than what it
  can observe. New claim `DEVIATION_ATTRIBUTION` requires T1-or-above **and** a present biomarker
  result (positive or negative). Supersedes ADR-0009, which retained the "no precondition" decision
  but on reasoning that had gone stale.
- `AttributionBasis` enum (`A0_NONE`, `A1_CLINICAL`, `A2_CONFIRMED`, `A3_EXCLUDED`) in
  `src/dte/tiers.py`. `A3_EXCLUDED` licenses attribution exactly as `A2_CONFIRMED` does: a negative
  result is frequently the more actionable of the two because it redirects toward a reversible cause.
- Scenarios S13-S17 in `tests/fixtures/tier_scenarios.json`, including the two that establish
  orthogonality (T3 without a biomarker is refused; T1 with one is permitted).
- Tests: 194 -> 223. New coverage for axis orthogonality, negative-result parity, A1 insufficiency,
  biomarker-cannot-rescue-an-empty-record, and refusal messages that name *which* axis failed.

### Changed
- `test_full_configuration_permits_every_claim` narrowed to tier-gated claims and renamed. It failed
  when the axis was added, which was correct - it encoded the pre-ADR-0013 invariant that tier alone
  determines everything. The replacement invariant is asserted separately, and the reason is recorded
  in the test body rather than in a commit message.
- `detect_tier()` takes an optional `attribution` argument defaulting to `A0_NONE`, so every existing
  caller is unaffected. The no-bypass signature test now also asserts this default.

### Known gaps
- **The fairness gate still certifies in aggregate, and now needs to certify per *cell*.** A 4x4
  tier-by-attribution grid has cells that will fall below `n >= 30` long before the aggregate does.
  This is the principal accepted cost of ADR-0013 and remains the most likely source of a future
  correctness defect.


All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — reference verification pass, July 2026

### Removed — unverifiable claims

Every numeric claim in this documentation was checked against PubMed or the issuing body.
Claims that could not be traced to a retrievable publication have been **removed**, together with
the reference entries that supported them. `docs/REFERENCES.md` records each removal and its
disposition.

Removed claims include: "~88% accuracy" for multimodal ensembles; "~81% vs ~73% for conventional
CSF analysis" for AI-EEG transition prediction; "15–20 point accuracy losses on minority
populations"; "~70% accuracy in under-represented populations"; "10–15% ambulatory EEG quality
degradation"; "~30% improvement in clinician confidence" from explainable AI; and "~18% improvement
in recall tasks" for personalised memory tools.

The design decisions those figures were used to justify are unchanged. They are now argued on their
own terms in the relevant ADRs rather than by appeal to an unverifiable number.

### Changed
- `docs/REFERENCES.md` rebuilt with full bibliographic detail and a DOI or URL for every entry.
  Previous revision contained 17 descriptive entries with no author, title or identifier.
- README performance comparison replaced with verified figures: AUC 0.89 / 77% accuracy for
  EEG+ERP discrimination of MCI [16]; stage-dependent AUCs of 0.98 / 0.84 / 0.78 [4]; and the
  methodological finding that a quarter of studies in this field have test-set problems [17].

## [Unreleased]

### Changed — architecture re-spine
- **The deployable core no longer requires neural hardware.** EEG is now an optional
  high-fidelity tier rather than the spine of the design ([ADR-0011](docs/adr/0011-non-neural-core.md)).
  Driven by published evidence that resting-state EEG classifiers reach only ~AUC 0.60 at the
  mild-cognitive-impairment stage, and that a plasma p-tau217 blood test outperforms dementia
  specialists by eighteen percentage points.
- Design targets in §7 are now indexed by tier rather than stated once for a single configuration.

### Added
- `src/dte/tiers.py` — four-tier fidelity ladder (T0 report / T1 ambient / T2 physiological /
  T3 neural) with claim ceilings enforced in code and no bypass path
  ([ADR-0010](docs/adr/0010-tiered-fidelity-ladder.md)).
- Tier is *derived from live signal availability on every evaluation*, never configured once.
  A patient whose headband is off is a T2 patient until it goes back on.
- `tests/test_tiers.py` — 27 tests functioning as an executable safety specification, including
  an assertion that no bypass parameter exists.
- `RiskModel.predict` raises `ClaimCeilingViolation` below T2; `OpportunityDetector.decide`
  returns silent below T3. The asymmetry is deliberate and documented.
- `RiskOutput.tier` and `OpportunityDecision.tier` — the tier is serialised with any output that
  depends on it, so a score cannot outlive the context justifying it.
- Caregiver outcomes promoted to primary endpoints; carer anxiety (GAD-7 at ≥6 months) added as a
  release-gating safety endpoint, per the Cochrane finding of potential carer-anxiety harm in
  reminiscence therapy ([ADR-0012](docs/adr/0012-caregiver-outcomes-as-primary.md)).

### Deprecated
- [ADR-0009](docs/adr/0009-no-biomarker-precondition.md) (no blood-biomarker precondition) is
  **under review**. Its cost-benefit has materially changed and must be re-argued rather than
  inherited.

## [0.1.0] — 2026-07-27

First public architecture release, derived from Chapter 3 of the source book
("Vision Translation to Technology Requirements").

### Added
- Complete C4-style architecture documentation set (`docs/01`–`docs/11`).
- Nine Architecture Decision Records under `docs/adr/`, each traceable to a Chapter 3 decision.
- FHIR R5 profiles and example resources for EEG, HRV, gait, cognitive assessment, risk score,
  cue delivery and consent (`schemas/fhir/`).
- JSON Schema definition of the Digital Twin state document (`schemas/json-schema/`).
- Runnable reference implementation (`src/dte/`): synthetic data generator, signal feature
  extraction, multimodal opportunity detector, contextual-bandit cue selector, ensemble risk
  model, decline simulator, subgroup fairness auditor, FHIR I/O, FastAPI service and CLI.
- Test suite, worked notebook, example scripts and GitHub Actions CI.
- `DISCLAIMER.md` establishing the illustrative status of all quantitative material.

### Changed
- Relicensed from an unrecognised "GGU License" to **Apache License 2.0**, chosen over MIT for its
  express patent grant (§3) and its `NOTICE` propagation requirement (§4d) — the latter means the
  "not a medical device" and "no real patient data" declarations travel with every fork.
- Added a `NOTICE` file carrying those declarations.
- Rewrote the root `README.md`. The previous version linked to eight files that did not exist and
  presented illustrative composite figures in a section headed "Research Validation". All figures
  are now explicitly labelled 🟡 ILLUSTRATIVE or 🔵 LITERATURE, and every link resolves.
