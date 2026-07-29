# ADR-0011: A non-neural core, with neural sensing as an optional tier

- **Status:** Accepted
- **Date:** 2026-07-27
- **Deciders:** Clinical owner, engineering lead, supervisor
- **Relates to:** [ADR-0002](0002-edge-first-neural-processing.md) (reframed, not superseded) ·
  [ADR-0009](0009-no-biomarker-precondition.md) (**requires revisiting — see below**) ·
  [ADR-0010](0010-tiered-fidelity-ladder.md) · [§7.6](../07-validation-and-benchmarks.md#76-the-weakest-link)

## Context

This architecture was built around EEG. §7.6 has always stated, honestly, that the inference from
"theta-band power is elevated relative to this person's baseline" to "this person is receptive to a
memory cue right now" is the least well-evidenced link in the system. That admission sat in the
validation chapter without changing anything upstream of it.

Two findings from the literature review force the issue. Neither is about adherence — at-home EEG
adherence in mild Alzheimer's dementia has been reported at around 77% over 52 weeks, against
roughly 55% typical for at-home monitoring in older populations, so people *will* wear the
headband if trained and supported.

**Finding 1 — the neural channel is weakest exactly where this system operates.** Resting-state EEG
classifiers separate Alzheimer's disease from age-matched controls at around AUC 0.85, and mild
cognitive impairment at **AUC 0.60** (Meghdadi et al., 2021, PLoS ONE 16(2):e0244180). An AUC of
0.60 is closer to chance than to clinical utility, and MCI is the population R1 targets. A
systematic review of 172 studies covering 234 experiments independently found that cognitive
assessment outperformed imaging for progression prediction, and that nearly a quarter of studies in
this field had test-set problems inflating reported performance (Ansart et al., 2020, *Medical
Image Analysis* 67:101848). A peer-reviewed scoping review of BCI for cognitive enhancement in
older people concludes it is "premature to make definitive claims about widespread BCI usability
and applicability" (Tsai et al., 2025, *BMC Geriatrics* 25(1):36).

**Finding 2 — the support burden, not the hardware, is the cost driver.** In the same at-home EEG
cohort, 49% of participants with dementia required technology support versus 17% of controls. That
is a staffing line per patient per month, and it is what makes the neural tier expensive.

**Finding 3 — reimbursement pays for care management, not sensing.** The Medicare GUIDE model pays
a monthly Dementia Care Management Payment per beneficiary. There is no mechanism that pays for
neural monitoring. A configuration nobody can bill for does not get deployed.

## Decision

**The deployable core of this system requires no neural hardware. EEG becomes an optional
high-fidelity tier that must earn its cost.**

- The base configuration (T1 in [ADR-0010](0010-tiered-fidelity-ladder.md)) is a smartphone and a
  caregiver. Conversion risk requires a wristband (T2). Neither requires EEG.
- The Memory Anchoring Pipeline remains a T3 capability. It is not degraded to run without neural
  input; below T3 it goes silent.
- **The value of the neural tier is treated as an open empirical question**, to be answered by the
  ablation described in §7.6 rather than assumed. A negative result — that disabling the neural
  channel does not degrade detection precision — remains a good outcome, and now has somewhere to
  land: the T3 tier is simply removed.

[ADR-0002](0002-edge-first-neural-processing.md) is **not superseded**. Its decision — that raw
neural data never leaves the device — remains correct and binding wherever neural sensing is
present. What changes is that its scope is now the optional tier rather than the whole system.

## Consequences

### Positive

- The architecture no longer rests its weight on its least-evidenced component.
- The base configuration is deployable in low- and middle-income settings, where roughly 71% of
  people with dementia will live by 2050, and where a headband plus a support technician is not a
  realistic per-patient cost.
- The economic argument becomes constructible. Collaborative dementia care management has an
  RCT-derived cost reduction of approximately $526 per beneficiary per month (Guterman et al.,
  2023, *JAMA Internal Medicine* 183(11):1222–1228), against a GUIDE care-management payment in the
  $65–390 range. A T1/T2 twin sits inside that economics. A T3 twin does not.
- §7.6 is promoted from a caveat to the organising principle of the design.

### Negative

- **Peak accuracy is sacrificed.** A configuration with every signal available will outperform T1.
  This is accepted on the same reasoning as ADR-0009: usable accuracy on the intended population
  beats peak accuracy on a narrower one.
- The Memory Anchoring Pipeline — the novel contribution of this work — is now explicitly the part
  with the least deployment path. That is uncomfortable and it is true.
- Significant rework across §1, §3, §4, §6, §7, §9 and §11.

## ⚠️ This forces ADR-0009 to be revisited

[ADR-0009](0009-no-biomarker-precondition.md) rejects blood biomarkers as a precondition, on
access-equity grounds, and accepts lower accuracy as the price. That reasoning was sound when
written. It is now much harder to sustain.

A prospective evaluation of a clinically available plasma p-tau217 test across 1,213 patients found
diagnostic accuracy of 88–92% in primary and secondary care. In the same study, **primary care
physicians achieved 61% accuracy** after clinical examination, cognitive testing and CT; **dementia
specialists achieved 73%**; the blood test achieved **91%** in both settings (Palmqvist et al.,
2024, *JAMA* 332(15):1245–1257).

The question ADR-0009 answered was "should we require an extra test that filters out the patients
we are trying to reach?" The question now is different: a single inexpensive blood draw
outperforms specialist judgement by eighteen percentage points, and a twin that declines to use it
in order to preserve access may be preserving access to a worse answer.

This ADR does not resolve that. It records that ADR-0009's cost-benefit has materially changed and
must be re-argued rather than inherited.
