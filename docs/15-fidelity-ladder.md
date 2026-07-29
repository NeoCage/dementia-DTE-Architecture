# 15. The Fidelity Ladder

> Implements [ADR-0010](adr/0010-tiered-fidelity-ladder.md) and [ADR-0011](adr/0011-non-neural-core.md).
> Reference implementation: [`src/dte/tiers.py`](../src/dte/tiers.py).
> Conformance suite: [`tests/fixtures/tier_scenarios.json`](../tests/fixtures/tier_scenarios.json).

---

## 15.1 Why the architecture has tiers

The original design assumed one configuration — EEG headband, wristband, phone, server — and had
one answer to the question *what can this twin claim?*

Real deployments do not look like that, and neither does a single patient across a single day. A
headband comes off. A wristband runs flat. A community health worker has a phone and nothing else.
The design needed a vocabulary for that, and more importantly a mechanism ensuring a twin with less
sensing cannot assert what a twin with more sensing could.

There is also an evidence argument, set out in [ADR-0011](adr/0011-non-neural-core.md). Resting-state
EEG classifiers reach roughly AUC 0.60 at the mild-cognitive-impairment stage — near chance, in the
population this system targets. A design that *requires* neural sensing puts its weight on its
least-evidenced component.

---

## 15.2 The four tiers

| Tier | Sensing added | Claim ceiling | Hardware envelope | Reimbursement fit |
|---|---|---|---|---|
| **T0 — Report** | Caregiver / clinician entry | Care-plan support, burden tracking. **No prediction.** | None | CPT 99483 |
| **T1 — Ambient** | + passive smartphone sensing | + deviation from personal baseline | A phone the household owns | GUIDE DCMP; CCM |
| **T2 — Physiological** | + wristband (HRV, actigraphy, IMU) | + MCI-to-dementia conversion risk | Phone + consumer wristband | GUIDE DCMP (higher complexity); RTM |
| **T3 — Neural** | + EEG headband | + real-time memory-cue opportunity | All of T2 + headband + support staffing | **None — research funding only** |

That last cell is the commercial argument for the whole ladder. There is no payment mechanism for
neural monitoring. A configuration nobody can bill for does not get deployed, however good it is.

---

## 15.3 Three properties that make it real

### Tier is derived, never configured

`detect_tier()` computes the tier from live signal availability **on every evaluation**. There is
no enrolment-time setting. A patient who was T3 this morning and took the headband off after lunch
is a T2 patient this afternoon, and the twin says so rather than continuing to score against stale
neural data.

### Tiers are contiguous

Signals are cumulative. A headband with no phone and no wristband yields **T0, not T3**. Skipping
levels would let a sparse configuration claim a fidelity its surrounding context cannot justify,
and neural data without behavioural context is exactly what the Memory Anchoring Pipeline must not
act on.

### The ceiling is enforced, with no bypass

`assert_claim_permitted()` raises `ClaimCeilingViolation`. There is no `force=True`. A test asserts
by introspection that no such parameter exists, so adding one fails the suite and requires an ADR
superseding ADR-0010.

---

## 15.4 Two failure modes, deliberately different

| Component | Below its tier | Why |
|---|---|---|
| `RiskModel.predict` | **raises** | A risk score without the sensing to justify it is a clinician acting on a fiction. |
| `OpportunityDetector.decide` | **returns silent** | A cue not delivered is a quiet afternoon. Silence is this pipeline's designed failure mode (P5). |

Degrading the MAP to a *lower-quality cue* would not be acceptable. Degrading it to silence is
exactly right.

---

## 15.5 The viability floor

T0 is the bottom of the ladder, but a record with **nothing** reporting — not even a caregiver
entry — sits below the floor. It is not a low-fidelity twin; it is an empty record, and an empty
record may not assert even care-plan support.

This distinction was not designed in. It was found by scenario **S09** when the data-driven
conformance suite failed against the first implementation, which happily permitted `CARE_PLAN` on
an empty record. That is the argument for keeping the scenarios in a file a clinician can read
rather than as parametrised cases buried in Python.

---

## 15.6 The scenario suite

[`tests/fixtures/tier_scenarios.json`](../tests/fixtures/tier_scenarios.json) holds twelve
clinically-recognisable situations. Each carries a narrative, the expected tier, the claims that
must be permitted and refused, and a `why_it_matters` note.

| ID | Scenario | Tier |
|---|---|---|
| S01 | Memory clinic intake, no devices issued | T0 |
| S02 | Community health worker deployment, phone only | T1 |
| S03 | Standard home deployment | T2 |
| S04 | Full research configuration | T3 |
| S05 | Headband removed mid-day | T3 → T2 |
| S06 | Wristband battery flat overnight | T2 → T1 |
| S07 | Headband present but no phone or wristband | T0 |
| S08 | Wristband with no phone to relay it | T0 |
| S09 | No signals at all | below floor |
| S10 | Unrecognised device in the signal set | T1 |
| S11 | Signal names with inconsistent casing | T2 |
| S12 | Fidelity restored when headband goes back on | T2 → T3 |

The file is kept separate from the test code for three reasons: the scenarios outlive this
implementation and can validate any future one; clinicians can review them without reading Python;
and they double as documentation and demo input.

### Running them

```bash
make test-tiers                                  # conformance suite
make replay-tiers                                # human-readable trace of all scenarios
PYTHONPATH=src python scripts/replay_tier_scenarios.py --id S05
PYTHONPATH=src python scripts/replay_tier_scenarios.py --json
```

In PyCharm, four run configurations are committed under [`.run/`](../.run/) and appear in the run
dropdown automatically: *All tests*, *Tier ladder - unit*, *Tier scenarios - data-driven*, and
*Replay tier scenarios (CLI)*. They set `PYTHONPATH` to `src/` so no manual interpreter
configuration is needed.

### Adding a scenario

Add an object to `scenarios` with an `id`, `name`, `narrative`, `signals`, `expected_tier`,
`permitted`, `forbidden` and `why_it_matters`. Optionally add `previous_signals` and
`expect_downgrade_note` to test a transition. The suite enforces that every scenario has a
narrative and a stated reason, and that every tier and every claim is exercised in both directions.

**When a scenario fails, decide whether the scenario is wrong or the code is.** Both are possible.
Neither should be changed without saying which.

---

## 15.7 What would retire a tier

The ladder is a hypothesis about where value sits, not a fixed structure.

- If prospective evaluation shows a T1 configuration matches T2 on conversion risk, the ceiling for
  `CONVERSION_RISK` drops to T1 and the wristband becomes optional.
- If the sham-controlled ablation in [§7.6](07-validation-and-benchmarks.md#76-the-weakest-link)
  shows that disabling the neural channel does not degrade detection precision, **T3 is removed
  entirely** and the Memory Anchoring Pipeline is rebuilt on T2 signals or abandoned.

That second outcome remains a good result. It is now a change to one table rather than a rewrite of
the architecture, which is the practical benefit of having built the ladder at all.
