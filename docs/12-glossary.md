# 12. Glossary

Plain-language definitions. If a term in this repository is not defined here, that is a documentation
bug — please [open an issue](../../../issues).

---

## Clinical terms

| Term | Meaning |
|---|---|
| **Alzheimer's disease (AD)** | The most common cause of dementia. A progressive brain disease affecting memory, thinking and behaviour. |
| **CDR** | Clinical Dementia Rating. A 0–3 scale. This system targets **0.5–1.0** (very mild to mild). |
| **Dementia** | An umbrella term for a decline in mental ability severe enough to interfere with daily life. Not a normal part of ageing. |
| **Episodic memory** | Memory for specific personal events — where you were, who you were with. The kind of memory the Memory Anchoring Pipeline tries to cue. |
| **MCI** | Mild Cognitive Impairment. A stage between normal ageing and dementia. Some people with MCI progress to dementia; many do not. Predicting who is requirement R1. |
| **MMSE / MoCA** | Mini-Mental State Examination / Montreal Cognitive Assessment. Standard pen-and-paper cognitive screening tests. |
| **Neurodegeneration** | Progressive loss of structure or function of brain cells. |
| **Nurse-navigator** | A nurse who coordinates care across services for patients with complex needs. A primary user of this system. |

## Technology terms

| Term | Meaning |
|---|---|
| **AR** | Augmented Reality. Overlaying digital content — here, a photograph — onto what someone sees. |
| **BCI** | Brain-Computer Interface. A system that reads brain activity and uses it to control or inform something. **This architecture uses only non-invasive BCI** (a headband, no surgery). |
| **Digital Twin (DT)** | A continuously updated virtual model of a real thing. Here, a statistical model of one person's cognitive and physiological state — **not** a 3-D brain rendering or a biophysical simulation. See [§3.0](03-digital-twin-engine.md#30-what-digital-twin-means-here--and-what-it-does-not). |
| **DTE** | Digital Twin Engine. The core service in this architecture. |
| **Edge computing** | Processing data on the device where it is collected (the patient's phone) instead of sending it to a server. Here it is a **privacy** decision, not just a performance one. |
| **EEG** | Electroencephalography. Measuring the brain's electrical activity with sensors on the scalp. Non-invasive, cheap, repeatable. |
| **Federated learning** | Training a shared model across several institutions where each keeps its own data, and only model updates are exchanged. **Documented but not implemented here.** |
| **FHIR (R5)** | Fast Healthcare Interoperability Resources, release 5. The international standard for exchanging healthcare data. |
| **MAP** | Memory Anchoring Pipeline. The real-time system that detects a memory-retrieval opportunity and delivers one personalised cue. |
| **SMART on FHIR** | A standard for launching a third-party app from inside an electronic health record, in the context of the patient already open on screen. |

## Signal and data terms

| Term | Meaning |
|---|---|
| **Artefact** | Contamination in a recording that isn't brain activity — muscle movement, a loose electrode, mains hum. Removing it is essential and hard. |
| **Band power** | How much EEG activity falls in a given frequency range. |
| **Delta / theta / alpha / beta / gamma** | EEG frequency bands: 0.5–4 / 4–8 / 8–13 / 13–30 / 30–45 Hz. **Theta** matters most here — associated with memory-retrieval readiness. |
| **Baseline (personal)** | This person's own normal range for a measure, learned from their own history. Requires ≥ 14 days before any alert can fire. **Central to the whole design.** |
| **Functional connectivity** | How coordinated activity is between different brain regions. |
| **Geofence** | A virtual boundary around a real place. Crossing it can trigger something. Opt-in and off by default here. |
| **HRV** | Heart Rate Variability. Variation in time between heartbeats. Used here as a rough proxy for agitation. |
| **IMU** | Inertial Measurement Unit. The accelerometer/gyroscope in a wearable. Used to detect movement and gate motion-contaminated EEG. |
| **RMSSD / SDNN / LF-HF** | Standard HRV measures. |
| **θ/α ratio** | Theta power divided by alpha power. A commonly used EEG marker in dementia research. |

## Machine learning terms

| Term | Meaning |
|---|---|
| **Calibration** | Whether a model's stated confidence matches reality. If it says 70%, does it happen 70% of the time? |
| **Contextual bandit** | A learning method that picks between options based on the current situation and learns from the result. Simpler and faster-converging than full reinforcement learning. Used to pick which cue to deliver. |
| **Drift** | When the real world changes so that a model's assumptions no longer hold, degrading it silently. |
| **Ensemble** | Combining several models. Used here because no single algorithm wins every dementia-prediction task. |
| **Explainability (XAI)** | Being able to say *why* a model produced an output. A hard requirement here, not a feature. |
| **Fairness gate** | An automatic check that blocks release if any demographic subgroup's accuracy is more than 10 points from the population average. |
| **Gradient-boosted trees / Random forest** | Two tree-based ML methods. Interpretable, data-efficient, and they run without a GPU. |
| **Sensitivity / False-positive rate** | How often the model correctly catches what it's looking for / how often it raises a false alarm. |
| **Shadow mode** | Running a model on live data where its output reaches no human. Used to validate safely. |
| **Subgroup gap** | The accuracy difference between a demographic group and the population average. |

## Project-specific terms

| Term | Meaning |
|---|---|
| **Alert Budget Governor** | The service that caps how many alerts a clinical team receives per week, against a ceiling the team itself agreed before launch. |
| **Cue** | A single personalised prompt — a photo, voice recording, sound or scent — intended to trigger a memory. |
| **Hard gate** | A condition that blocks a cue outright, regardless of how confident the system is. Agitation is one. |
| **Illustrative (🟡)** | A number produced from synthetic data or a narrative composite. **Not a clinical result.** |
| **Literature (🔵)** | A number from a published, cited study about someone else's work. |
| **Refractory period** | The minimum time after one cue before another can fire. Prevents nagging. |
| **Silence** | A first-class outcome. The system's default. Logged as a decision, not an absence. |
| **Six-question gate** | The requirement-approval discipline in [§2.2](02-requirements-and-traceability.md#22-the-six-question-gate). |
| **"St. Mercy Medical Center"** | **A narrative composite. Not a real hospital.** A teaching device used throughout the source book. Any figure attributed to it is illustrative. See [`../DISCLAIMER.md`](../DISCLAIMER.md). |
| **Twin state** | The current snapshot of one person's model: features, baseline, trajectory, learned preferences, consent, provenance. |
