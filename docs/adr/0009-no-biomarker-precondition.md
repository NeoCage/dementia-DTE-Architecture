# ADR-0009: Do not require blood-based biomarkers at intake

- **Status:** Superseded by [ADR-0013](0013-biomarker-as-attribution-axis.md) on 2026-07-30
- **Why superseded:** Its revisit trigger was tested and found one-third met; its stated R1 feature
  set had gone stale against ADR-0011; and the conversion-risk claim it was defending has been
  withdrawn. The "no precondition" decision is *retained* by ADR-0013 - only the reasoning and the
  mechanism changed. Kept unedited below as the record of what was decided in July 2026.
- **Date:** 2026-07-27
- **Deciders:** Clinical owner, patient/family representative, data-governance officer
- **Relates to:** R1 · [§2.3](../02-requirements-and-traceability.md#23-requirement-r1--earlier-more-reliable-mci-to-dementia-risk-identification)

## Context

Blood-based biomarkers for Alzheimer's pathology have improved substantially and can add real
predictive signal, relatively cheaply. The obvious move is to include them in the R1 feature set.

The counter-argument is about **who gets excluded**, and it is decisive.

Requiring an extra test at intake adds a step: a phlebotomy appointment, a lab turnaround, a cost that
may not be reimbursed, and a reason to defer enrolment. Every added step filters the population, and
it does not filter randomly. It filters out people with less time, less money, less transport, less
health-system fluency and less trust in medical institutions.

Those are, precisely, the patients most likely to be missed by current annual screening in the first
place — the population R1 exists to reach.

A model that performs better on a cohort that excludes the people you were trying to help has not
solved the problem. It has re-described it.

There is a second, narrower point: making a biomarker a *precondition* also interacts badly with the
fairness gate ([ADR-0007](0007-subgroup-fairness-gate.md)). If the biomarker requirement systematically
thins enrolment in some subgroups, those subgroups fall below `n ≥ 30`, the gate cannot certify them,
and the documented intended population has to be narrowed — excluding them formally as well as
practically.

## Decision

**Blood-based biomarkers are not required for enrolment or for a risk score to be produced.**

- The R1 feature set at launch is: resting-state EEG, structured neuropsychological scores, ≥ 2 visits
  spanning 6–12 months, and medication/comorbidity history from the EHR.
- Biomarkers are supported as an **optional enrichment**. Where a result already exists in the record,
  the model may use it.
- The model must produce a valid, gated, explained score **without** them. A missing biomarker is
  never treated as a reason to withhold a score.

## Consequences

### Positive
- Enrolment requires nothing the patient is not already doing, which keeps the reachable population
  wide.
- Avoids a systematic exclusion that would show up later as an uncertifiable subgroup.
- Lowers cost per patient — material in the LMIC contexts where the burden is heaviest.
- Consistent with the Stage 1 discipline of naming what is genuinely off the table
  ([§6.2](../06-ml-architecture.md#62-stage-1--problem-definition)).

### Negative
- **Accuracy is likely lower than a biomarker-inclusive model would achieve.** Accepted deliberately.
  We are trading peak accuracy on a narrower cohort for usable accuracy on the intended one.
- Two model variants (with and without biomarker features) means two validation burdens if the optional
  path is used.
- Some clinicians will reasonably argue the biomarker version should be default where available.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Require biomarkers | Higher accuracy, systematically excludes the target population. Solves a different problem. |
| Require them only where already reimbursed | Creates a two-tier system where model quality tracks a patient's insurance status. |
| Impute missing biomarkers | Imputing a pathology marker from correlated features is confidently wrong in exactly the ambiguous cases that matter. |

## How this is enforced

- Biomarker features are optional in the feature schema; the model trains and scores with them absent.
- Validation is run on the no-biomarker path as the primary configuration.

## Revisit if

Blood-based biomarker testing becomes routine, reimbursed and low-friction at the point of intake — at
which point the exclusion argument weakens and this should be reconsidered.
