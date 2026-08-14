# ADR-0013: Biomarker status as an attribution axis, not a precondition

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Clinical owner, patient/family representative, data-governance officer
- **Supersedes:** [ADR-0009](0009-no-biomarker-precondition.md)
- **Relates to:** [ADR-0007](0007-subgroup-fairness-gate.md) · [ADR-0010](0010-tiered-fidelity-ladder.md) ·
  [ADR-0011](0011-non-neural-core.md) · [ADR-0012](0012-caregiver-outcomes-as-primary.md)

## Context

ADR-0009 decided that blood-based biomarkers must not be a precondition for enrolment or for a
score. Its stated revisit trigger was: *"Blood-based biomarker testing becomes routine, reimbursed
and low-friction at the point of intake."*

That trigger has been tested and it is **one-third met**.

| Condition | Status, July 2026 |
|---|---|
| **Routine** | Partly. The FDA cleared the first blood biomarker test for Alzheimer's diagnosis (plasma pTau217/Aβ1-42 ratio) on 16 May 2025, for symptomatic patients aged 55 and over. Independent work reports primary-care diagnostic accuracy of ~93% against ~94% for specialists across 1,310 patients. But surveys of rural providers find ~75% not ordering biomarker testing and ~62% reporting they do not feel qualified to order it. |
| **Reimbursed** | No. Legislation that would extend Medicare coverage to earlier biomarker testing is pending and has not passed. Pre-symptomatic screening is not covered. Anticipated out-of-pocket cost is $500–1,000. |
| **Low-friction** | Partly. A venepuncture is far less burdensome than a lumbar puncture or a $3,000–6,000 PET scan, but it remains a draw, a lab turnaround, and a clinician who must feel competent to order and interpret it. |

ADR-0009's exclusion argument therefore survives, and is now **quantified rather than predicted**:
the ~75% non-ordering rate among rural providers is the filtering mechanism ADR-0009 anticipated,
measured.

Two things in ADR-0009 are nevertheless wrong and must be corrected.

**It is internally stale.** ADR-0009 states the R1 launch feature set as "resting-state EEG,
structured neuropsychological scores, ≥ 2 visits spanning 6–12 months, and medication/comorbidity
history." [ADR-0011](0011-non-neural-core.md) demoted EEG to an optional high-fidelity tier. Two
accepted records currently disagree about what the base configuration is.

**The claim it was defending has been withdrawn.** ADR-0009 framed biomarkers as a feature-set
question for a conversion-risk model. The regulatory and evidential analysis now recommends
**withdrawing the conversion-risk claim** rather than defending it: the existing device
classification for a computerised cognitive assessment aid covers interpretation of *current*
function and explicitly excludes identifying the presence or absence of a clinical diagnosis, and
prospective single-person prediction of conversion remains unestablished.

So the biomarker question does not get resolved in ADR-0009's favour. **It moves.** Once the twin
stops forecasting conversion, amyloid status is no longer an input to a prognosis. But it remains
highly relevant to a different question, and that question turns out to be the one the pilot
actually surfaced.

### The question the pilot surfaced

In the first forty households, what the navigator found was overwhelmingly **not** cognitive
deterioration. It was a diuretic taken in the evening, a daytime supervision arrangement that had
quietly collapsed, and caregivers who had not slept properly in weeks. Nearly all of these are
reversible; nearly all of them produce a cognitive event four to eight weeks later if left alone.

This means the twin's most valuable discrimination is not *will this person convert* but:

> **Is this deviation more likely attributable to neurodegeneration, or to something reversible?**

That is an **attribution** question, not a prognostic one. It is answerable, clinically actionable,
and it is exactly the question a biomarker result informs.

## Decision

**Biomarker status becomes a second, orthogonal axis governing what the twin may assert about the
cause of an observed deviation. It remains not a precondition for anything.**

The claim ceiling becomes a function of two independent inputs:

- **Sensing tier** (T0–T3, [ADR-0010](0010-tiered-fidelity-ladder.md)) — governs *what the twin can
  observe*.
- **Attribution basis** (this ADR) — governs *what the twin may say about why*.

### The attribution axis

| Basis | Meaning |
|---|---|
| `A0_NONE` | No biomarker information. The default, and never a barrier. |
| `A1_CLINICAL` | A clinical diagnosis exists in the record, without biomarker confirmation. |
| `A2_CONFIRMED` | A biomarker result is present and positive for the relevant pathology. |
| `A3_EXCLUDED` | A biomarker result is present and negative. |

Two properties are deliberate and both matter.

**`A3_EXCLUDED` is as informative as `A2_CONFIRMED`.** A negative result licenses the twin to say
that an observed deviation is *less* likely attributable to Alzheimer's pathology, which is a
clinically useful statement and is the one most likely to redirect a clinician toward a reversible
cause. An axis that only rewarded positives would waste half the information.

**The axis is orthogonal to the tier, not a rung above it.** A household at T1 with a confirmed
biomarker and a household at T3 with none are different in kind, not in degree, and neither
dominates the other. Collapsing them onto one scale would be exactly the category error the
fidelity ladder exists to prevent.

### What each cell permits

The new claim is `DEVIATION_ATTRIBUTION`. It requires **T1 or above** (there must be a deviation to
attribute) **and** `A2_CONFIRMED` or `A3_EXCLUDED` (there must be a basis for attributing it).

No existing claim's requirements change. `CARE_PLAN`, `DEVIATION`, `CONVERSION_RISK` and
`CUE_OPPORTUNITY` keep their tier thresholds exactly as ADR-0010 set them.

`CONVERSION_RISK` is retained in the enum and remains **withdrawn as a product claim**. It is not
removed from the code, because removing it would silently allow a future caller to reintroduce the
behaviour without encountering the ceiling. Keeping it, gated, is the safer state.

## Consequences

### Positive

- Enrolment still requires nothing the patient is not already doing. The equity argument that
  motivated ADR-0009 is preserved intact.
- Where a biomarker result already exists, its value is used and — crucially — **made visible in the
  output** rather than silently folded into a score. A clinician can see which basis the attribution
  rests on.
- The most clinically valuable output is now the one the evidence best supports: separating probable
  neurodegeneration from a reversible cause.
- A negative biomarker becomes actionable rather than merely reassuring.
- Consistent with [ADR-0012](0012-caregiver-outcomes-as-primary.md): the reversible causes the axis
  helps surface are disproportionately caregiver- and household-level.

### Negative

- **The validation surface becomes two-dimensional.** The fairness gate already certifies models in
  aggregate rather than per tier, which is recorded as the most likely source of a future
  correctness defect. This ADR makes that worse: the gate should certify per *cell*, and a
  four-by-four grid has cells that will fall below the `n ≥ 30` threshold long before the aggregate
  does. **This is the principal cost of this decision and it is accepted knowingly.**
- Two-tier care risk is not eliminated, only made visible. Households with a biomarker result will
  receive a more specific output than those without, and that difference will track insurance
  status. Making it visible is better than hiding it; it is not the same as solving it.
- More states means more scenarios to review clinically, and the scenario file grows.
- An `A3_EXCLUDED` result may be over-read as "nothing is wrong." Non-Alzheimer's dementias exist and
  a negative amyloid result does not exclude them. The explanation text must say so explicitly.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Keep ADR-0009 unchanged | Leaves the stale EEG-based feature set contradicting ADR-0011, and leaves a genuinely useful attribution capability unbuilt. |
| Require a biomarker for conversion-risk claims | Re-introduces the exclusion ADR-0009 was written to prevent, and defends a claim the regulatory analysis recommends withdrawing. |
| Add biomarker as a fifth sensing tier above T3 | Wrong shape. Biomarker status is not a sensing fidelity and does not sit in an ordered relationship with neural data. Would imply a household with a blood test is "higher fidelity" than one with continuous physiology. |
| Impute biomarker status from correlated features | Rejected in ADR-0009 and still rejected. Imputing a pathology marker is confidently wrong in exactly the ambiguous cases that matter. |

## How this is enforced

- `AttributionBasis` is an enum in `src/dte/tiers.py`; `TierState` carries it as a field defaulting
  to `A0_NONE`, so existing callers are unaffected.
- `permits()` evaluates both axes. `assert_claim_permitted()` raises `ClaimCeilingViolation` naming
  *which* axis failed, so an operator can tell a missing sensor from a missing biomarker.
- Scenarios S13–S17 in `tests/fixtures/tier_scenarios.json` cover the new cells, including the
  T3-without-biomarker and T1-with-biomarker cases that establish orthogonality.
- There is no bypass parameter, and the existing signature-introspection test is extended to
  cover the two-axis form.

## Revisit if

- The fairness gate is made per-cell and the resulting cell counts prove unworkable at realistic
  enrolment volumes — in which case the axis should be collapsed to a binary
  (`basis known` / `basis unknown`) rather than four states.
- Biomarker testing becomes genuinely reimbursed and routinely ordered in primary care, at which
  point `A0_NONE` becomes rare and the axis stops earning its validation cost.
- A non-amyloid biomarker panel becomes available that speaks to non-Alzheimer's dementias, which
  would require the axis to name the pathology rather than assume one.
