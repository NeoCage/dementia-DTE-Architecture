# Documentation Index

> ⚠️ **Read [`../DISCLAIMER.md`](../DISCLAIMER.md) first.** Every number in these documents is
> labelled either 🟡 **ILLUSTRATIVE** (synthetic or narrative-composite, not a clinical result) or
> 🔵 **LITERATURE** (a cited published finding about someone else's study). Nothing here has been
> validated on real patients.

This folder contains the full technical architecture for the **Dementia Digital Twin Engine (DTE)**
and the **Memory Anchoring Pipeline (MAP)**.

---

## Pick a reading path

**"I have ten minutes and I want to know what this is."**
→ [`../README.md`](../README.md), then [§1 Architecture Overview](01-architecture-overview.md).

**"I'm a clinician or care leader. Would this actually work on my ward?"**
→ [§2 Requirements](02-requirements-and-traceability.md) → [§7 Validation](07-validation-and-benchmarks.md)
→ [§10 Governance & Ethics](10-governance-and-ethics.md) → [§11 Roadmap](11-implementation-roadmap.md).
You can skip every other document.

**"I'm a software or ML engineer. How is it built?"**
→ [§1 Overview](01-architecture-overview.md) → [§3 Digital Twin Engine](03-digital-twin-engine.md)
→ [§4 Memory Anchoring Pipeline](04-memory-anchoring-pipeline.md) → [§6 ML Architecture](06-ml-architecture.md)
→ [`adr/`](adr/) → then run the code in [`../src/dte/`](../src/dte/).

**"I'm a data or integration engineer."**
→ [§5 Data Architecture](05-data-architecture.md) → [`../schemas/`](../schemas/)
→ [§8 Security & Privacy](08-security-and-privacy.md).

**"I'm a researcher, reviewer or examiner. Where does this come from?"**
→ [§2 Requirements](02-requirements-and-traceability.md) (traces every design decision back to the
source book) → [`adr/`](adr/) (records *why* each decision was made) → [`REFERENCES.md`](REFERENCES.md).

**"I'm a person living with dementia, or a caregiver."**
→ [§10 Governance & Ethics](10-governance-and-ethics.md) is written to be read without technical
background, and [`../DISCLAIMER.md`](../DISCLAIMER.md) explains plainly what this is and is not.
Your critique is welcome — see [`../CONTRIBUTING.md`](../CONTRIBUTING.md#clinical-and-lived-experience-review).

---

## Full contents

| # | Document | What it answers |
|---|---|---|
| 1 | [Architecture Overview](01-architecture-overview.md) | What the system is, who it serves, the seven tiers, and the quality attributes it is designed against. |
| 2 | [Requirements & Traceability](02-requirements-and-traceability.md) | The three business requirements, the six-question gate each had to pass, and a table tracing every architectural component back to a requirement. |
| 3 | [Digital Twin Engine](03-digital-twin-engine.md) | Component-level design of the DTE: twin state store, fusion service, simulator, personalisation, explainability. |
| 4 | [Memory Anchoring Pipeline](04-memory-anchoring-pipeline.md) | How a real-time memory-retrieval opportunity is detected and a cue selected, delivered and scored. |
| 5 | [Data Architecture](05-data-architecture.md) | FHIR R5 as the canonical model, the seven data flows, retention, lineage and the content library. |
| 6 | [ML Architecture](06-ml-architecture.md) | The five-stage methodology, model choices, feature engineering, training and MLOps. |
| 7 | [Validation & Benchmarks](07-validation-and-benchmarks.md) | The numeric gates the system must pass before each release, including the subgroup fairness gate. |
| 8 | [Security & Privacy](08-security-and-privacy.md) | Threat model, neural-data protections, consent architecture, and the controls the reference code does *not* implement. |
| 9 | [Deployment Architecture](09-deployment-architecture.md) | Edge / gateway / cloud split, environments, scale economics, and operating an additive-not-replacement rollout. |
| 10 | [Governance & Ethics](10-governance-and-ethics.md) | Who is accountable, how consent works, the ethical position on surveillance, and the resistance the system will meet. |
| 11 | [Implementation Roadmap](11-implementation-roadmap.md) | Six phases from single-clinic pilot to multi-site federation, with go / no-go criteria. |
| 12 | [Glossary](12-glossary.md) | Every acronym and term, defined in plain language. |
| [15](15-fidelity-ladder.md) | The Fidelity Ladder — tiers, claim ceilings, and the scenario suite | 20 min |
| — | [Architecture Decision Records](adr/) | Thirteen records of *why* the significant choices were made, and what was rejected. |
| — | [References](REFERENCES.md) | Numbered citation list used throughout. |

## Diagram sources

All diagrams are written in [Mermaid](https://mermaid.js.org/) and render natively on GitHub.
Standalone `.mmd` sources are in [`../diagrams/`](../diagrams/) so they can be exported for a
thesis, slide deck or poster.
