#!/usr/bin/env python3
"""Verify that every quantitative claim in prose carries an illustrative/literature label.

Run: python scripts/check_labels.py

WHY THIS EXISTS
---------------
The single largest integrity risk in this repository is a synthetic or narrative-composite figure
being read as a clinical finding. Prose is where that happens: a reader skims a percentage in a
sentence and remembers it as a result. So every figure in prose must sit near a 🟡 ILLUSTRATIVE or
🔵 LITERATURE marker, or in an explicit target/benchmark context.

WHAT IS DEFERRED, AND WHY
-------------------------
* **Fenced code blocks** are skipped. They hold decision traces and command output whose status is
  established by the section heading above them; every such section here carries a marker.
* **URLs** are stripped before matching, because badge and link URLs contain `%20` escapes that look
  like percentages.
* Labels are matched within a **±3 line window**, not on the same line, because a marker frequently
  sits in the sentence before or after the figure it governs.

This is a heuristic backstop for review, not a substitute for it.
"""

from __future__ import annotations

import pathlib
import re
import sys

LABEL = re.compile(
    r"(ILLUSTRATIVE|LITERATURE|🟡|🔵|SYNTHETIC|synthetic|illustrative|composite|"
    r"target|Target|TARGET|benchmark|Benchmark|threshold|Threshold|"
    r"minimum|Minimum|maximum|Maximum|ceiling|not a real|NOT real|not real|"
    r">=|<=|≥|≤)"
)
FIGURE = re.compile(r"\b\d{1,3}(\.\d+)?\s?(%|percent)\b|\bn\s?=\s?\d+")
URL = re.compile(r"\(https?://[^)]*\)|https?://\S+|`[^`]*`")

WINDOW = 3
TARGETS = ["README.md", "DISCLAIMER.md", "docs"]


def scan(path: pathlib.Path) -> list[str]:
    problems: list[str] = []
    lines = path.read_text().splitlines()
    in_fence = False
    fence_flags = []
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            fence_flags.append(True)  # the fence marker line itself
            continue
        fence_flags.append(in_fence)

    # Rebuild aligned flags (the loop above skips fence markers, so redo it cleanly).
    fence_flags = []
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            fence_flags.append(True)
        else:
            fence_flags.append(in_fence)

    stripped = [URL.sub(" ", ln) for ln in lines]

    for i, line in enumerate(stripped):
        if fence_flags[i]:
            continue
        if not FIGURE.search(line):
            continue
        lo, hi = max(0, i - WINDOW), min(len(stripped), i + WINDOW + 1)
        context = " ".join(stripped[lo:hi])
        if not LABEL.search(context):
            problems.append(f"{path}:{i + 1}: unlabelled figure -> {lines[i].strip()[:100]}")
    return problems


def main() -> int:
    files: list[pathlib.Path] = []
    for t in TARGETS:
        p = pathlib.Path(t)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.md")))
        elif p.is_file():
            files.append(p)

    problems: list[str] = []
    for f in files:
        problems.extend(scan(f))

    if problems:
        print("Unlabelled quantitative claims found.")
        print("Label each 🟡 ILLUSTRATIVE (synthetic/composite) or 🔵 LITERATURE (cited study).\n")
        print("\n".join(problems))
        return 1

    print(f"all quantitative claims labelled across {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
