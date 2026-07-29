#!/usr/bin/env python3
"""Validate schema files, and require every FHIR example to be labelled as synthetic test data.

Run: python scripts/check_schemas.py

The HTEST security label is not decoration. It is the machine-readable marker that stops a synthetic
example resource from being mistaken for a real record if it is ever loaded into a FHIR server.
"""

from __future__ import annotations

import json
import pathlib
import sys


def main() -> int:
    problems: list[str] = []
    checked = 0

    for f in sorted(pathlib.Path("schemas").rglob("*.json")):
        checked += 1
        try:
            d = json.loads(f.read_text())
        except json.JSONDecodeError as exc:
            problems.append(f"{f}: invalid JSON: {exc}")
            continue

        if f.parent.name != "fhir":
            continue

        rt = d.get("resourceType")
        if not rt:
            problems.append(f"{f}: missing resourceType")
            continue

        labels = [s.get("code") for s in d.get("meta", {}).get("security", [])]
        if "HTEST" not in labels:
            problems.append(f"{f}: missing HTEST security label (synthetic-data marker)")

        if rt == "Bundle":
            for i, entry in enumerate(d.get("entry", [])):
                if "resource" not in entry:
                    problems.append(f"{f}: entry[{i}] has no resource")

    if problems:
        print("Schema problems found.\n")
        print("\n".join(problems))
        return 1

    print(f"{checked} schema files valid and correctly labelled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
