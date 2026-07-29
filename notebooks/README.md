# Notebooks

| Notebook | Contents |
|---|---|
| [`01_synthetic_cohort_analysis.ipynb`](01_synthetic_cohort_analysis.ipynb) | Full worked analysis path: cohort generation, signal pipeline and its quality gate, risk model training with explanations, the fairness gate blocking a release, and a simulated day of the Memory Anchoring Pipeline. |

> ⚠️ Every figure produced here is 🟡 **ILLUSTRATIVE**, from synthetic data. No real patient
> contributed to any number. See [`../DISCLAIMER.md`](../DISCLAIMER.md).

```bash
pip install -r ../requirements-dev.txt
jupyter notebook 01_synthetic_cohort_analysis.ipynb
```

Outputs are **not** committed. Notebook output diffs are unreadable in review, and committed plots
of synthetic data are the easiest way for an illustrative figure to end up quoted as a finding.
