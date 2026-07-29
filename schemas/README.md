# Schemas

> ⚠️ **Every example in this folder uses fabricated identifiers and synthetic values. No real patient
> data is present, and none may ever be added.** See [`../DISCLAIMER.md`](../DISCLAIMER.md).

Two schema families, serving two different jobs.

| Folder | Standard | Purpose |
|---|---|---|
| [`fhir/`](fhir/) | HL7 FHIR R5 | **Exchange format.** Everything crossing the interoperability tier. System of record. |
| [`json-schema/`](json-schema/) | JSON Schema 2020-12 | **Internal format.** The denormalised Digital Twin state document used for low-latency reads. |

Why both: FHIR is verbose and normalised for interoperability, which makes it a poor fit for "give me
this person's current state and baseline in one read". The twin document is a projection rebuilt from
FHIR resources. **FHIR remains the system of record** — if the twin document is lost it can be fully
reconstructed; if the FHIR store is lost, the record is gone.

Rationale: [ADR-0001](../docs/adr/0001-fhir-r5-canonical-model.md) ·
[§5 Data Architecture](../docs/05-data-architecture.md)

---

## FHIR R5 resources

| File | Resource | Represents |
|---|---|---|
| [`patient.json`](fhir/patient.json) | `Patient` | Pseudonymised subject — **no real identifiers** |
| [`device.json`](fhir/device.json) | `Device` | EEG headband, with firmware version recorded |
| [`consent.json`](fhir/consent.json) | `Consent` | Per-modality, revocable provisions |
| [`eeg-band-power.json`](fhir/eeg-band-power.json) | `Observation` | EEG band power + θ/α ratio + data-quality components |
| [`hrv-observation.json`](fhir/hrv-observation.json) | `Observation` | RMSSD, SDNN, LF/HF, derived agitation index |
| [`gait-observation.json`](fhir/gait-observation.json) | `Observation` | Gait speed, stride variability, walking-bout length |
| [`cognitive-assessment.json`](fhir/cognitive-assessment.json) | `Observation` | MoCA / MMSE, LOINC-coded |
| [`caregiver-burden.json`](fhir/caregiver-burden.json) | `Observation` | Validated caregiver-burden instrument score |
| [`risk-assessment.json`](fhir/risk-assessment.json) | `RiskAssessment` | MCI→dementia risk **with `basis` carrying the explanation** |
| [`detected-issue-deviation.json`](fhir/detected-issue-deviation.json) | `DetectedIssue` | Baseline-deviation alert with evidence |
| [`cue-delivery-procedure.json`](fhir/cue-delivery-procedure.json) | `Procedure` + `Observation` | A delivered memory cue and the observed response |

### The two mappings worth understanding

**Risk output is a `RiskAssessment`, not an `Observation`.** `RiskAssessment.basis` is designed to hold
the evidence a prediction rests on — which is exactly where the explainability payload belongs. The
consequence is that **explanations travel with the score** through any FHIR-conformant system, rather
than living only in our own UI. If the score is exported, the reasons go with it.
See [ADR-0006](../docs/adr/0006-explainability-as-a-hard-requirement.md).

**A memory cue is a `Procedure`.** It is an intervention performed on a patient with an intended
therapeutic effect, delivered autonomously to a cognitively vulnerable person. It must appear in the
record as something that *happened to them*, visible to audit. Modelling it as a lesser resource type
would make it invisible.

## Coding systems used

| System | URI | Used for |
|---|---|---|
| LOINC | `http://loinc.org` | Observations, cognitive instruments |
| SNOMED CT | `http://snomed.info/sct` | Clinical findings, procedures |
| UCUM | `http://unitsofmeasure.org` | Units |
| Project-local | `https://github.com/NeoCage/.../CodeSystem/dte` | Concepts with no standard code yet (EEG band power, cue modality). **Local codes are a gap, not a design choice** — contributions mapping them to standard terminologies are welcome. |

## Validating the examples

```bash
# Structural validation of every example
python -c "
import json, pathlib
for f in sorted(pathlib.Path('fhir').glob('*.json')):
    d = json.loads(f.read_text())
    print(f'{f.name:38} {d.get(\"resourceType\", d.get(\"entry\") and \"Bundle\")}')
"
```

For full FHIR conformance validation, use the
[official HL7 validator](https://github.com/hapifhir/org.hl7.fhir.core) — these examples are
structurally valid R5 but have not been run through profile validation, which a real deployment must do.
