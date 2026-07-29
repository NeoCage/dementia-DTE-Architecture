"""Subgroup fairness gate. Implements ADR-0007 and docs/07-validation-and-benchmarks.md §7.4."""

from dte.fairness.subgroup import FairnessReport, SubgroupMetrics, evaluate_fairness

__all__ = ["FairnessReport", "SubgroupMetrics", "evaluate_fairness"]
