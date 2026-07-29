# Disclaimer — Read This First

> **Read this page before you read any number anywhere else in this repository.**

This repository is a **reference architecture**. It is a detailed, opinionated blueprint for how a
Digital Twin and Brain-Computer Interface system for dementia care *could* be built, together with
runnable code that demonstrates the design on **synthetic data**.

It is not a product, not a clinical system, and not evidence that any of this has been built and
tested on real patients.

---

## 1. This is not a medical device

This software has **not** been evaluated, cleared or approved by the FDA, EMA, MHRA, CDSCO, or any
other regulatory authority. It must not be used to diagnose, treat, cure, prevent or monitor any
disease, or to inform any clinical decision about any real person.

If you are a patient or a caregiver: nothing here is medical advice. Speak to a qualified clinician.

---

## 2. All quantitative results in this repository are illustrative, not clinical

This is the most important thing on this page.

Every performance figure, pilot table, outcome metric and quote in this repository falls into one
of two categories, and each is labelled where it appears:

| Label | Meaning |
|---|---|
| 🟡 **ILLUSTRATIVE** | A worked example. Produced from a narrative composite scenario or from the synthetic data generator in this repository. **No real patient contributed to it.** It exists to show what an evaluation *would look like*, not to report what happened. |
| 🔵 **LITERATURE** | A figure taken from a published, cited source. Traceable to a reference in [`docs/REFERENCES.md`](docs/REFERENCES.md). It describes someone else's study, not this system. |

### About "St. Mercy Medical Center"

**St. Mercy Medical Center is a narrative composite. It is not a real hospital.**

It is a teaching device used throughout the source book to illustrate how a real health system
would work through the requirements, methodology and rollout decisions described here. Any pilot
table, participant count (such as `n=28`), outcome percentage or caregiver quote attributed to
St. Mercy — anywhere in this repository or in the book — is an **illustrative worked example**,
generated to demonstrate an analysis method.

**No clinical trial has been conducted. No real patient data has been collected, processed or
analysed by this system. No IRB-approved study underlies any number in this repository.**

If you cite this work, cite it as a proposed architecture and a methodology. Do not cite any
number in it as a clinical result. Doing so would misrepresent the evidence base.

---

## 3. No real data is in this repository, and none should ever be added

The repository contains **zero** real patient data, and it must stay that way.

- All data used by the code is produced at runtime by `src/dte/data/synthetic.py`.
- `.gitignore` excludes generated data directories.
- Contributing real, identifiable or re-identifiable patient data — including "de-identified"
  EEG, which is increasingly understood to be re-identifiable — is grounds for immediate rejection
  of a pull request. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## 4. The architecture is unvalidated

The design targets in [`docs/07-validation-and-benchmarks.md`](docs/07-validation-and-benchmarks.md)
— such as ≥80% sensitivity for MCI-to-dementia conversion, or a ≤10 percentage-point accuracy gap
between demographic subgroups — are **targets the system would have to hit before deployment**.
They are not measurements. Nothing in this repository has been measured against a real cohort.

Any organisation adopting this architecture is responsible for its own clinical validation,
regulatory pathway, ethics approval, data protection impact assessment and post-market
surveillance.

---

## 5. Known limitations of the reference implementation

- Models are trained on synthetic data with hand-authored generative assumptions. Their accuracy
  reflects those assumptions, not biological reality.
- The federated learning tier is described in documentation but is **not implemented** in code.
- Signal processing is simplified: real ambulatory EEG artefact rejection is substantially harder
  than what is demonstrated here.
- The AR / audio / scent cue delivery layer is simulated as function calls. No hardware driver is
  included.
- Security controls are described in [`docs/08-security-and-privacy.md`](docs/08-security-and-privacy.md)
  but the reference API implements **no** authentication. It is a local demonstration server only
  and must never be exposed to a network.

---

## 6. Ethical position

Dementia care technology can slide easily into surveillance. This architecture takes an explicit
position on that, documented in [`docs/10-governance-and-ethics.md`](docs/10-governance-and-ethics.md):
the person living with dementia is a participant with standing to refuse, not a monitored object.
Consent is continuous and revocable, neural data is treated as a special category requiring
heightened protection, and every requirement must deliver a benefit the patient or family can
actually perceive — not only a benefit to the clinician or the institution.

If you fork this work, please carry that position with it. The Apache 2.0 `NOTICE` file
([`NOTICE`](NOTICE)) requires you to carry the "not a medical device" and "no real patient data"
declarations forward; the ethical position above is not legally enforceable, and is asked for
rather than required.
