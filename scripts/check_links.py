#!/usr/bin/env python3
"""Verify every internal markdown link and heading anchor resolves.

Run: python scripts/check_links.py

A reference architecture whose cross-references are broken is much less useful than one with fewer
of them, so this runs in CI. External URLs are counted but not fetched.

ANCHOR SLUGS
------------
GitHub's algorithm: lowercase, strip formatting characters, drop anything that is not a word
character / space / hyphen, then replace EACH space with a hyphen. That last step matters — spaces
are not collapsed, so a heading containing " — " (em dash, which is dropped) yields a DOUBLE hyphen
in the slug. Getting this wrong produces a wave of false positives.
"""

from __future__ import annotations

import pathlib
import re
import sys
import urllib.parse

LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING = re.compile(r"^#{1,6}\s+(.*)$")

# GitHub-relative shorthands that are valid on github.com but are not filesystem paths.
GITHUB_SHORTHAND = re.compile(r"^(\.\./)+(issues|pulls|discussions|wiki|actions)(/|$|\?)")


def slugify(heading: str) -> str:
    s = heading.strip().lower()
    s = re.sub(r"<[^>]+>", "", s)  # inline HTML
    s = re.sub(r"[`*_~]", "", s)  # markdown emphasis
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)  # links -> their text
    s = re.sub(r"[^\w\s-]", "", s)  # drop punctuation, em dashes, emoji
    return s.replace(" ", "-")  # NOT \s+ -> "-": GitHub does not collapse


def main() -> int:
    repo = pathlib.Path(".").resolve()
    md_files = [p for p in sorted(pathlib.Path(".").rglob("*.md")) if ".git" not in p.parts]

    anchors: dict[str, set[str]] = {}
    for f in md_files:
        found: set[str] = set()
        in_fence = False
        for line in f.read_text().splitlines():
            if line.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = HEADING.match(line)
            if m:
                found.add(slugify(m.group(1)))
        anchors[str(f)] = found

    broken: list[str] = []
    ok = external = shorthand = 0

    for f in md_files:
        for i, line in enumerate(f.read_text().splitlines(), 1):
            for text, target in LINK.findall(line):
                if target.startswith(("http://", "https://", "mailto:")):
                    external += 1
                    continue
                if GITHUB_SHORTHAND.match(target):
                    shorthand += 1
                    continue
                if target.startswith("#"):
                    if slugify(target[1:]) in anchors[str(f)]:
                        ok += 1
                    else:
                        broken.append(f"{f}:{i}: anchor '{target}' not in this file  [{text[:40]}]")
                    continue

                path_part, _, frag = target.partition("#")
                resolved = (f.parent / urllib.parse.unquote(path_part)).resolve()
                if not resolved.exists():
                    broken.append(f"{f}:{i}: missing path '{target}'  [{text[:40]}]")
                    continue
                if frag and resolved.suffix == ".md":
                    try:
                        rel = str(resolved.relative_to(repo))
                    except ValueError:
                        rel = None
                    if rel in anchors and slugify(frag) not in anchors[rel]:
                        broken.append(f"{f}:{i}: anchor '#{frag}' not in {rel}  [{text[:40]}]")
                        continue
                ok += 1

    print(
        f"internal links OK: {ok} | github shorthand: {shorthand} | "
        f"external (unchecked): {external} | BROKEN: {len(broken)}"
    )
    if broken:
        print()
        print("\n".join(broken))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
