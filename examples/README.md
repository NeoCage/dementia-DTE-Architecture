# Examples

Small, self-contained scripts. Each demonstrates one architectural property and prints what it is
demonstrating, so the output is readable without reading the code first.

All data is synthetic. See [`../DISCLAIMER.md`](../DISCLAIMER.md).

```bash
PYTHONPATH=src python examples/01_agitation_veto.py
PYTHONPATH=src python examples/02_fairness_gate_blocks.py
PYTHONPATH=src python examples/03_personal_baseline.py
PYTHONPATH=src python examples/04_fhir_round_trip.py
```

| Script | Demonstrates |
|---|---|
| `01_agitation_veto.py` | A cue is blocked despite maximal confidence, because physiology vetoes rather than votes |
| `02_fairness_gate_blocks.py` | The gate blocks on a measured gap **and** on a subgroup too small to certify |
| `03_personal_baseline.py` | The same measurement is normal for one person and alarming for another |
| `04_fhir_round_trip.py` | A risk score serialised as FHIR `RiskAssessment` carries its explanation in `basis` |
