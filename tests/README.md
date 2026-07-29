# Tests

Run with `make test` (or `PYTHONPATH=src pytest -q`).

These are not only regression tests. **Several of them are executable specifications of safety
properties**, and a failure means the architecture's stated guarantees no longer hold — not merely
that a function changed.

| File | Guards |
|---|---|
| `test_signals.py` | Artefact rejection; the quality gate refusing to infer from junk; the agitation index remaining reachable when inputs are missing |
| `test_fusion.py` | The agitation veto; all six hard gates; silence as the default outcome |
| `test_policy.py` | Reward asymmetry; distress suppression; missing feedback never imputed as success |
| `test_models.py` | A risk score being impossible without ≥3 ranked features; point-estimate suppression on wide intervals; no imputation of missing features |
| `test_fairness.py` | The subgroup gate blocking on a large gap **and** on an uncertifiable subgroup |
| `test_twin.py` | Personal baseline establishment; no alerting before it; consent gating reads; provenance on every write |
| `test_api.py` | The demo API's routes and its explicit not-for-deployment warnings |

If you weaken one of these, `CONTRIBUTING.md` requires an Architecture Decision Record — not just
a passing test suite.
