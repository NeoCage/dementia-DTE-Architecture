# ADR-0006: Treat explainability as a release gate, not a feature

- **Status:** Accepted
- **Date:** 2026-07-27
- **Deciders:** Clinical owner, model owner, patient/family representative
- **Relates to:** R1, R2 · [§3.8](../03-digital-twin-engine.md#38-explainability-service) · Principle P3

## Context

The usual treatment of explainability is as a feature on a roadmap: ship the model, add explanations
later when there is time. There never is time.

The evidence says that ordering is backwards. Clinicians who can see why a model reached its conclusion
adopt it at meaningfully higher rates than clinicians handed an opaque score (🔵 [18]). Clinician
resistance to this class of tool is a **trust** problem, not a technology-literacy problem — which
means it cannot be solved by more training on an unexplained score.

There is also a harder point. Explainability is not primarily about comprehension; it is about
**contestability**. A clinician's real question is not "why did it say 0.72?" but "is it right about
*this* patient?" They can only answer that if they can see what the model relied on and check it
against what they know that the model does not.

## Decision

**No model output reaches a human without its reasoning attached. There is no bypass path.**

- The Explainability Service sits structurally between every model and every clinician-facing surface.
- Every risk score carries **≥ 3 ranked contributing features**, each with direction, magnitude, and a
  plain-language gloss ("theta-band power elevated 1.8 SD above this patient's own baseline").
- Every deviation alert states which feature deviated, by how much, over what window, versus which
  baseline.
- Every trajectory states which observations anchor it and its confidence interval.
- **Explanation coverage of 100% is a release gate (B1.5).** A build where any output can reach a
  human unexplained fails.

The patient-facing counterpart is different in kind, not just in wording: a plain-language summary
developed **jointly with the patient-and-family advisory council**, stating what the score means, what
it does not mean (a risk estimate, not a diagnosis), and what happens next.

## Consequences

### Positive
- Constrains model selection toward inherently interpretable methods
  ([ADR-0004](0004-ensembles-over-deep-networks.md)) — a good constraint here.
- Makes the system contestable, which makes it safe: a clinician who can see the reasoning can catch
  a model relying on something spurious.
- Directly addresses the dominant form of clinician resistance.
- Feeds the EU AI Act high-risk technical documentation requirement.
- Because the explanation rides in `RiskAssessment.basis`, it travels with the score into any
  FHIR-conformant system ([ADR-0001](0001-fhir-r5-canonical-model.md)).

### Negative
- Rules out model classes that might be more accurate.
- Screen space is scarce in an EHR risk panel; ranked features must be terse.
- Feature importances can themselves mislead — a highly-weighted feature is not necessarily causal.
  Mitigated by clinician training that says so explicitly, and by wording explanations as
  contributions rather than causes.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Explanations as an optional detail view | Optional means unused under time pressure, which is exactly when a wrong score does damage. |
| Post-hoc SHAP over a black box | Better than nothing, but post-hoc explanation of a model you cannot inspect is not contestable in the way clinicians need. |
| Score only; train clinicians to trust the validation | Assumes trust follows evidence. The literature says it follows visible reasoning (🔵 [18]). |
| Explanations for clinicians only, not patients | Rejected by the patient/family representative. A patient told they are high-risk with no explanation has been given anxiety, not information. |

## How this is enforced

- The output contract for every model includes `top_features`; a model that cannot populate it cannot
  be registered.
- CI asserts explanation coverage; below 100% fails the build.
- No API route returns a score without its `basis`.

## Revisit if

A model class emerges that is both materially more accurate and genuinely interpretable — in which
case this ADR is satisfied, not superseded.
