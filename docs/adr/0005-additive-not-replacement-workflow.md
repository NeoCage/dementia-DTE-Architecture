# ADR-0005: Integrate additively into existing workflow; never replace it

- **Status:** Accepted
- **Date:** 2026-07-27
- **Deciders:** Clinical informaticist, nurse-navigator lead, clinical owner
- **Relates to:** R1, R2 · [§9.1](../09-deployment-architecture.md#91-the-governing-decision-additive-not-replacement) · Principle P6

## Context

The single highest-leverage decision a team makes is whether a new AI system is positioned as an
addition to existing clinical workflow or a replacement for it.

A clean replacement is often more efficient on paper. Consolidating three tools into one purpose-built
interface is better design in the abstract.

It also fails, reliably, because **clinical staff cannot absorb a brand-new system while also being
expected to keep patients safe that same week.** The adoption cost is paid during a period when the
staff have no spare capacity, and the tool loses.

The Care Ecosystem's spread across a network of health systems is the counter-example that worked: it
was built from day one to sit inside existing care-coordination roles, not to require a new role
nobody had budgeted for (🔵 [7][20]). And AI decision tools succeed when clinicians help design them
from the start through real iterative feedback, rather than receiving a finished product and being
told to adopt it (🔵 [20]).

## Decision

**Every output surfaces inside a tool the user already opens. No new logins, no new dashboards, no new
committees.**

| Output | Additive placement |
|---|---|
| EEG risk score | Inside the **existing EHR risk panel**, beside cardiovascular and fall-risk scores clinicians already trust |
| Deviation alerts | **Extend** the nurse-navigator's existing care-coordination dashboard |
| Governance | **Add AI-specific review criteria** to the existing clinical-quality and technology-investment committees |

The governance row is as important as the technical ones. Standing up a new AI oversight committee from
nothing means creating a body with no institutional authority and no clinician trust, and waiting years
for it to acquire both. Existing committees already have them.

A corollary on rollout ordering: **Release 1 attaches no automated action at all.** The score appears
as a passive flag to one physician. The purpose is to let clinicians build trust in the model's
reasoning before it touches a single workflow decision.

## Consequences

### Positive
- Adoption cost is near zero — the user opens the same screen they already open.
- Inherits the existing tool's authentication, audit and training.
- Failure is graceful: if the system is switched off, the underlying workflow is unchanged because it
  was never removed.
- Governance inherits existing authority rather than trying to manufacture it.

### Negative
- **We are constrained by the host tool's UI.** EHR risk panels are cramped and inflexible, which
  limits how much explanation can be shown inline (mitigated by a SMART on FHIR detail view).
- EHR integration work is slow, vendor-dependent and politically involved.
- Some genuinely better interaction designs are unavailable.
- Adding criteria to an existing committee means competing for agenda time.

### Accepted costs
- The family app is the one standalone surface — justified because no existing tool serves families —
  and it is deliberately held to Release 3.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Standalone purpose-built clinical app | Better UX, full control. Requires a new login nobody opens. This is precisely the pattern the failed first-attempt scenario describes. |
| Replace the existing risk panel entirely | Cleaner information architecture, unacceptable change-management cost during a period when staff have none. |
| New dedicated AI governance committee | Sounds rigorous. Has no authority and no clinician trust for its first several years. |
| Email or messaging alerts | Zero integration cost. Guarantees alert fatigue and produces no audit trail. |

## How this is enforced

- The clinician surface is a SMART on FHIR app launched from EHR patient context — it has no
  independent login by design.
- The nurse surface ships as an extension to the existing dashboard, not a separate deployment.

## Revisit if

An organisation is greenfield with no existing EHR risk panel or care-coordination dashboard, in which
case "additive" has nothing to add to.
