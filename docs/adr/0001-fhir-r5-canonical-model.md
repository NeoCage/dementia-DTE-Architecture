# ADR-0001: Use FHIR R5 as the canonical data model

- **Status:** Accepted
- **Date:** 2026-07-27
- **Deciders:** Clinical informaticist, data-governance officer, lead engineer
- **Relates to:** R1, R2, R3 · [§5 Data Architecture](../05-data-architecture.md)

## Context

The system ingests four kinds of data that natively share nothing: EEG features from a consumer
headset, wearable telemetry, EHR clinical records, and caregiver-reported logs. Each vendor has its
own format.

The tempting shortcut is a lean internal JSON format designed around our first use case, with adapters
per source. It is faster to build for use case #1.

The evidence argues against it. Organisations that delay investing in standards-based integration tend
to discover the real cost of that delay on their **second or third** use case, not their first
(🔵 [6]). By then the internal format has calcified into the shape of the original requirement, every
new source needs a bespoke adapter, and nothing exports cleanly to anyone else's system.

There is also a research constraint: multi-institutional collaboration is necessary because almost no
single institution has enough patients to train something robust (🔵 [5]). Collaboration across
institutions on a bespoke format is impractical.

## Decision

**Every piece of clinical data crossing the interoperability tier is an HL7 FHIR R5 resource.** No
bespoke format leaves the edge tier.

Inside the DTE, a denormalised twin-state document is used for low-latency reads, but it is a
*projection* — FHIR remains the system of record and the twin document is fully reconstructible from
it.

Two specific mappings are load-bearing:
- Risk output is a **`RiskAssessment`**, not an `Observation`, because `RiskAssessment.basis` is
  designed to carry the evidence a prediction rests on. Explainability then travels with the score
  through any FHIR-conformant system rather than living only in our UI.
- A delivered memory cue is a **`Procedure`**, because it is an intervention performed on a patient
  and must be visible to audit as something that happened to them.

## Consequences

### Positive
- Adding a fourth requirement should require zero new integration work at the data layer. This is the
  practical test of whether the decision was implemented correctly.
- SMART on FHIR gives us EHR embedding almost free, which is what makes
  [ADR-0005](0005-additive-not-replacement-workflow.md) achievable.
- Federation and external validation become tractable.
- Regulatory documentation is easier — FHIR is a recognised standard.

### Negative
- Significantly more work for the first use case. FHIR is verbose and its learning curve is real.
- Some concepts (EEG band power, cue delivery) have no clean off-the-shelf profile and need custom
  profiling with LOINC/SNOMED coding.
- FHIR's verbosity makes it unsuitable for the hot read path, which is why the twin document exists —
  accepted duplication.

### Accepted costs
- Terminology service dependency.
- Profile maintenance as FHIR evolves.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Bespoke internal JSON + per-source adapters | Fast for use case #1, pathological by use case #3. The exact pattern [6] documents. |
| OMOP CDM | Excellent for retrospective research, poor for real-time exchange and device data. Not mutually exclusive — an OMOP export can sit downstream. |
| FHIR R4 | More widely deployed today, but R5 has materially better device and observation support. Chose forward compatibility. |
| openEHR | Strong clinical modelling, far weaker device/wearable ecosystem and less EHR-vendor support. |

## How this is enforced

- Every example resource in [`../../schemas/fhir/`](../../schemas/fhir/) is a valid R5 resource.
- The interop tier accepts only profile-conformant resources; validation failure rejects the write.
- No serialisation path exists from the internal twin document to an external consumer.

## Revisit if

FHIR R6 changes the device or observation model materially, or a regulator mandates a different
exchange standard in a target jurisdiction.
