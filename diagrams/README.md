# Diagram sources

All diagrams in this repository are written in [Mermaid](https://mermaid.js.org/) and render
natively on GitHub inside the documentation. The `.mmd` files here are standalone copies so they can
be exported for a thesis, slide deck, or poster.

## Rendering to an image

```bash
npm install -g @mermaid-js/mermaid-cli

# Single diagram to SVG (best for print / thesis)
mmdc -i 01-system-context.mmd -o 01-system-context.svg

# All diagrams to PNG at 2x scale
for f in *.mmd; do mmdc -i "$f" -o "${f%.mmd}.png" -s 2 -b transparent; done
```

## Contents

| File | Appears in | Shows |
|---|---|---|
| `01-system-context.mmd` | [docs §1.4](../docs/01-architecture-overview.md#14-system-context-c4-level-1) | C4 Level 1 — who and what the system talks to |
| `02-seven-tiers.mmd` | [docs §1.5](../docs/01-architecture-overview.md#15-the-seven-tiers-c4-level-2--containers) | C4 Level 2 — the seven tiers and the privacy boundary |
| `03-two-loops.mmd` | [docs §1.6](../docs/01-architecture-overview.md#16-the-two-decision-loops) | Fast (memory) vs slow (clinical) decision loops |
| `04-map-pipeline.mmd` | [docs §4.3](../docs/04-memory-anchoring-pipeline.md#43-full-pipeline) | Full Memory Anchoring Pipeline, including all six hard gates |
| `05-fairness-gate.mmd` | [docs §7.4](../docs/07-validation-and-benchmarks.md#74-the-subgroup-fairness-gate) | The subgroup fairness gate decision flow |
| `06-roadmap.mmd` | [docs §11.1](../docs/11-implementation-roadmap.md#111-six-phases) | Six deployment phases with stop conditions |

Rendered images are **not** committed — they are reproducible from source, and binary diffs make
review harder. `.gitignore` excludes common image outputs in this directory.
