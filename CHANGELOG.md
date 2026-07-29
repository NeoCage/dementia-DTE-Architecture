# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
