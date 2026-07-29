"""Dementia Digital Twin Engine (DTE) — reference implementation.

WHAT THIS IS
------------
A runnable demonstration of the architecture documented in ``docs/``. Every module cites the
architecture section it implements, so the code and the specification can be read together.

WHAT THIS IS NOT
----------------
This is NOT a medical device and NOT clinical software. It has no authentication, no encryption,
no audit logging and no consent enforcement. It operates exclusively on synthetic data generated
at runtime by :mod:`dte.data.synthetic`.

Read ``DISCLAIMER.md`` before drawing any conclusion from any number this package produces.
"""

__version__ = "0.1.0"

NOT_A_MEDICAL_DEVICE = True
USES_SYNTHETIC_DATA_ONLY = True

__all__ = ["__version__", "NOT_A_MEDICAL_DEVICE", "USES_SYNTHETIC_DATA_ONLY"]
