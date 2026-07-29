#!/usr/bin/env python3
"""Scan for anything resembling real patient data.

Run: python scripts/check_data_safety.py

Enforces rule 1 of CONTRIBUTING.md: never contribute real patient data. This is a crude heuristic
backstop that catches the obvious cases — a committed spreadsheet, a pasted record, an email address
in an example. It is NOT a substitute for review, and it cannot detect a re-identifiable EEG file.
"""

from __future__ import annotations

import pathlib
import re
import sys

PATTERNS = {
    "US Social Security number": r"\b\d{3}-\d{2}-\d{4}\b",
    "UK NHS number": r"\b\d{3}\s\d{3}\s\d{4}\b",
    "email address": r"[A-Za-z0-9._%+-]+@(?!example\.(org|com))[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "MRN-like identifier": r"\bMRN[:\s-]*\d{6,}\b",
    "full date of birth": r"\bDOB[:\s]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
}

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".ipynb", ".gif", ".zip", ".pyc", ".so"}
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "venv", "artifacts"}
# Files that legitimately contain a contact address or citation metadata.
ALLOW = {"CITATION.cff", "README.md", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md"}


def main() -> int:
    hits: list[str] = []
    for f in pathlib.Path(".").rglob("*"):
        if not f.is_file() or f.suffix.lower() in SKIP_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in f.parts) or f.name in ALLOW:
            continue
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for label, pat in PATTERNS.items():
            for m in re.finditer(pat, text):
                hits.append(f"{f}: possible {label}: {m.group(0)[:40]}")

    if hits:
        print("Possible real patient data detected. See CONTRIBUTING.md rule 1.\n")
        print("\n".join(hits[:40]))
        return 1

    print("no patterns resembling real patient data found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
