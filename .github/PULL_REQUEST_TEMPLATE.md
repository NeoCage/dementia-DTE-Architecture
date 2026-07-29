## What this changes

<!-- One or two sentences. -->

## Why

<!-- Link an issue if there is one. -->

---

## Data safety checklist — required

- [ ] This PR contains **no real patient data**, in any form — not raw, not aggregated, not
      "de-identified". (EEG and gait signals are increasingly understood to be re-identifiable.)
- [ ] Any new quantitative figure is labelled either 🟡 **ILLUSTRATIVE** (synthetic or
      narrative-composite) or 🔵 **LITERATURE** (with a citation in `docs/REFERENCES.md`).
- [ ] No new personally identifying example values (names, real dates of birth, MRNs, emails).

## Architecture checklist

- [ ] This does **not** weaken a safety, fairness or consent control. If it does, I have added an
      Architecture Decision Record and referenced it below.
- [ ] ADR reference (if applicable): `ADR-____`
- [ ] Documentation updated where behaviour changed, so code and docs still agree.
- [ ] `make lint` passes.
- [ ] `make test` passes.

## Bias and fairness — required for any change to a model, feature, threshold or training procedure

- [ ] Not applicable to this PR.

If applicable:

- Subgroups evaluated: <!-- at minimum: age band, sex, and one proxy for under-representation -->
- Largest accuracy gap vs. population average: <!-- % -->
- Does it exceed the 10 percentage-point gate in `docs/07-validation-and-benchmarks.md`? <!-- yes/no -->
- Does this change make any model output less explainable? If so, why is that acceptable?

<!--
The published literature documents accuracy falling by 15-20 points on under-represented
populations in exactly this class of model. A fairness check that is skipped once tends to stay
skipped.
-->
