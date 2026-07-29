# ADR-0002: Process neural data at the edge; raw EEG never leaves the device

- **Status:** Accepted
- **Date:** 2026-07-27
- **Deciders:** Data-governance officer, security lead, lead engineer, patient/family representative
- **Relates to:** R1, R3 · [§8 Security & Privacy](../08-security-and-privacy.md) · Principle P2

## Context

Raw EEG is roughly 256 samples/second × 8–16 channels, continuously. Three things make centralising it
a bad idea:

1. **It is highly identifying.** EEG has person-discriminative properties comparable to a biometric.
   "De-identified EEG" is a much weaker guarantee than the phrase suggests.
2. **It reveals more than was consented to.** Signals collected to assess memory-retrieval readiness
   also carry information about mood, attention and cognitive load.
3. **The population has fluctuating capacity to consent.** The people this system serves are the least
   able to police their own privacy — which raises, not lowers, our obligation.

Separately, the fast loop needs sub-2-second latency, and a cloud round-trip on a mobile network
cannot reliably deliver that.

Processing at the edge cuts latency and shrinks the volume of sensitive neural data that ever needs to
travel anywhere, which makes the privacy conversation with regulators, ethics committees and families
considerably easier.

## Decision

**All raw neural time-series is processed on the patient's device and discarded there.** Only derived
features cross the network boundary.

Specifically:
- Raw EEG lives in a **60-second ring buffer in memory**. It is never written to disk.
- Artefact rejection, band-power extraction and connectivity computation run on-device.
- The opportunity detector runs on-device, so the fast loop works fully offline.
- **No API, debug flag, or support-mode override exists that uploads raw EEG.**

That last point is the decision. The control is enforced **by absence of capability**, not by policy.
A policy saying "we don't upload raw data" is one urgent hotfix away from being false. A system with no
code path to do it is not.

## Consequences

### Positive
- Removes an entire class of privacy risk rather than mitigating it.
- Fast loop works with no connectivity — on a train, in a basement, with data switched off.
- Makes GDPR special-category handling and DPIA sign-off dramatically simpler.
- Reduces bandwidth and server storage cost, which matters in LMIC contexts.
- Device theft exposes almost nothing: 60 seconds of buffer.

### Negative
- **We cannot retrospectively reprocess raw data with a better algorithm.** If a superior artefact
  method appears, it must be deployed to devices; historical recordings cannot be improved. This is a
  genuine and permanent research cost, accepted deliberately.
- Debugging signal-quality problems in the field is materially harder.
- Feature extraction must run within a mid-range phone's compute and battery budget.
- Any new feature requiring raw signal must be implemented on-device or dropped.

### Accepted costs
- On-device model updates need their own deployment pipeline.
- Cross-device consistency in feature extraction must be tested explicitly.

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Upload raw, process centrally | Best for research flexibility, worst for privacy. Creates a central store of biometric-grade neural data — the single most attractive target in the system. |
| Upload raw with client-side encryption | Server still holds the ciphertext; key compromise or lawful-access demand exposes everything. Moves the risk, does not remove it. |
| Upload a downsampled or windowed subset | Still uploads neural time-series, still re-identifiable, and gives up the offline capability without eliminating the risk. |
| Edge processing with a raw-upload flag for consented research | Rejected specifically because a flag that exists gets turned on. If a research study needs raw EEG, it should collect it under its own protocol and consent — not through this system. |

## How this is enforced

- The edge tier exposes no raw persistence or transmission function.
- The ring buffer is fixed-size and in-memory by construction.
- Code review rejects any PR introducing a raw upload path, regardless of guard conditions.

## Revisit if

A future requirement genuinely cannot be met on-device *and* an ethics committee, a data-governance
officer and the patient/family representative all independently agree the trade is warranted.
Unanimity is the bar.
