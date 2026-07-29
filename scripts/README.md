# Scripts

Repository health checks. All three run in CI, and all three are runnable locally.

| Script | Enforces |
|---|---|
| [`check_labels.py`](check_labels.py) | Every quantitative claim in prose carries a 🟡 ILLUSTRATIVE or 🔵 LITERATURE label |
| [`check_data_safety.py`](check_data_safety.py) | No content resembling real patient data (`CONTRIBUTING.md` rule 1) |
| [`check_schemas.py`](check_schemas.py) | Schemas parse, and every FHIR example carries the `HTEST` synthetic-data label |

```bash
make check     # runs all three
```

These are heuristic backstops, not substitutes for review. `check_data_safety.py` in particular
cannot detect a re-identifiable EEG file — only obvious textual leaks.
