# Contributing

Thank you for considering a contribution. This project sits at the intersection of clinical care,
neural data and machine learning, so the contribution rules are stricter than a typical open-source
repository. Please read all of this before opening a pull request.

---

## The three hard rules

**1. Never contribute real patient data.**
Not raw, not aggregated, not "de-identified". EEG and gait signals are increasingly understood to
be re-identifiable, and this repository has no lawful basis, consent framework or safeguarding
process for holding personal health data. Any PR containing something that looks like real patient
data will be closed and the branch deleted. If you need data, extend
`src/dte/data/synthetic.py`.

**2. Never present a number as a clinical result.**
Every quantitative claim added to this repository must be labelled either 🟡 **ILLUSTRATIVE**
(synthetic or narrative-composite) or 🔵 **LITERATURE** (with a citation in
[`docs/REFERENCES.md`](docs/REFERENCES.md)). Unlabelled figures will be rejected. See
[`DISCLAIMER.md`](DISCLAIMER.md) for why this matters more here than elsewhere.

**3. Never weaken a safety, fairness or consent control without an ADR.**
Removing an artefact-rejection step, relaxing the subgroup fairness gate, defaulting consent to
"on", or making an explainability output optional are architectural changes, not implementation
details. They require an Architecture Decision Record. See below.

---

## Ways to contribute

| Contribution | Where it goes | Notes |
|---|---|---|
| Fixing an error in the architecture | `docs/` | Open an issue first if it changes a design decision. |
| Correcting or adding a citation | `docs/REFERENCES.md` | Peer-reviewed sources preferred. |
| A new architecture decision | `docs/adr/` | Use the ADR template. |
| Improving the reference code | `src/dte/` | Must come with tests. |
| Extending the synthetic generator | `src/dte/data/synthetic.py` | Document your generative assumptions. |
| A clinical or lived-experience critique | GitHub Issues | Genuinely welcome — see below. |
| Improving accessibility of documentation | anywhere | Especially welcome. |

### Clinical and lived-experience review

If you are a clinician, a person living with a dementia diagnosis, or a caregiver, your critique is
more valuable to this project than a code contribution and does not require any technical
knowledge. Open an issue with the `clinical-review` or `lived-experience` label and say plainly
what is wrong, unrealistic, or would not survive contact with a real Tuesday afternoon. The
architecture assumes a patient-and-family advisory representative holds effective veto over
patient-facing design; that principle applies to this repository too.

---

## Architecture Decision Records

Any change to *how the system is structured* — not just how a function is written — needs an ADR.

1. Copy `docs/adr/0000-template.md` to `docs/adr/NNNN-short-title.md`, incrementing `NNNN`.
2. Fill in Context, Decision, Consequences, and Alternatives Considered.
3. Link the ADR from `docs/adr/README.md`.
4. Reference the ADR number in your pull request.

An ADR is never edited once merged. If a decision is reversed, write a new ADR that supersedes it
and mark the old one `Superseded by ADR-NNNN`.

---

## Development setup

```bash
git clone https://github.com/NeoCage/dementia-DTE-Architecture.git
cd github.com-dementia-DTE-Architecture

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
make dev
make test
```

## Code standards

- **Python ≥ 3.9**, formatted and linted with `ruff` (`make lint`).
- **Type hints on all public functions.** This code is read far more often than it is run.
- **Docstrings explain *why*, not *what*.** A reader should be able to trace a function back to the
  section of the architecture it implements. Existing code cites its source doc in the module
  docstring; please follow that convention.
- **Tests for every behavioural change** (`make test`). Bug fixes need a test that fails before the
  fix.
- **No new runtime dependency without justification** in the PR description. A dependency that
  cannot run on a modest community-hospital server is a dependency this project probably cannot
  accept — see ADR-0004.

## Pull request process

1. Branch from `main` (`feature/...`, `fix/...`, or `docs/...`).
2. Make sure `make lint` and `make test` both pass.
3. Fill in the pull request template, including the data-safety checklist.
4. Small, focused pull requests get reviewed. Large ones sit.

## Bias and fairness checklist

Any change touching a model, a feature, a threshold or a training procedure must state in the PR
description:

- Which subgroups the change was evaluated across (at minimum: age band, sex, and one proxy for
  under-representation in the training distribution).
- The largest accuracy gap between any subgroup and the population average, and whether it exceeds
  the 10 percentage-point gate defined in `docs/06-validation-and-benchmarks.md`.
- Whether the change makes any model output less explainable, and if so, why that is acceptable.

The published literature documents accuracy falling by fifteen to twenty points on under-represented
populations in exactly this class of model. A fairness check that is skipped once tends to stay
skipped.

## Code of Conduct

Participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Licence and patent grant

Contributions are accepted under the [Apache License 2.0](LICENSE).

By submitting a pull request you confirm two things:

1. You have the right to license your contribution under those terms.
2. Per **§5** of the licence, your contribution is submitted under the same terms as the Work —
   which, per **§3**, includes an express grant of any patent claims of yours that your contribution
   necessarily infringes.

That second point is deliberate and worth stating plainly rather than leaving in the legal text.
This field has an active patent landscape. A reference architecture is only useful if people can
build on it without fear that a contributor will later assert a patent over the very technique they
contributed. If you are not in a position to grant that, please open an issue describing the idea
instead of submitting code — a well-described issue is still a valuable contribution.

If you add a new source file, you do **not** need to paste the licence header into it; the
repository-level `LICENSE` and `NOTICE` cover the whole Work.
