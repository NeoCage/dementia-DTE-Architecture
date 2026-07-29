"""Synthetic data generation and FHIR I/O.

There is no loader for real patient data in this package, and none may be added.
See ``CONTRIBUTING.md`` and ``DISCLAIMER.md``.
"""

from dte.data.synthetic import (
    SyntheticCohort,
    generate_cohort,
    generate_day,
    generate_eeg,
    generate_rr_intervals,
)

__all__ = [
    "SyntheticCohort",
    "generate_cohort",
    "generate_day",
    "generate_eeg",
    "generate_rr_intervals",
]
