"""Shared fixtures."""

from __future__ import annotations

import numpy as np
import pytest

from dte.data.synthetic import generate_cohort, generate_eeg, generate_rr_intervals


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(1234)


@pytest.fixture
def clean_eeg(rng: np.random.Generator):
    return generate_eeg(artefact_rate=0.05, rng=rng)


@pytest.fixture
def dirty_eeg(rng: np.random.Generator):
    return generate_eeg(artefact_rate=0.85, rng=rng)


@pytest.fixture
def calm_rr(rng: np.random.Generator) -> np.ndarray:
    return generate_rr_intervals(agitated=False, rng=rng)


@pytest.fixture
def agitated_rr(rng: np.random.Generator) -> np.ndarray:
    return generate_rr_intervals(agitated=True, rng=rng)


@pytest.fixture(scope="session")
def cohort():
    return generate_cohort(n=300, seed=42)
