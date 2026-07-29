#!/usr/bin/env python3
"""Replay the tier scenarios and print what the twin would do in each.

Runs the same fixture the conformance suite uses (``tests/fixtures/tier_scenarios.json``), but
prints a human-readable trace rather than asserting. Useful for demonstrating the fidelity ladder
to a clinical audience, and for checking by eye that a change to the ceiling table does what you
intended.

    PYTHONPATH=src python scripts/replay_tier_scenarios.py
    PYTHONPATH=src python scripts/replay_tier_scenarios.py --id S05
    PYTHONPATH=src python scripts/replay_tier_scenarios.py --json

In PyCharm: use the committed "Replay tier scenarios (CLI)" run configuration.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from dte.tiers import (  # noqa: E402
    Claim,
    ClaimCeilingViolation,
    assert_claim_permitted,
    detect_tier,
    downgrade_note,
)

FIXTURE = REPO / "tests" / "fixtures" / "tier_scenarios.json"

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _colour(enabled: bool, code: str) -> str:
    return code if enabled else ""


def replay(scenario: dict, colour: bool = True) -> dict:
    g, r, d, b, x = (
        _colour(colour, GREEN),
        _colour(colour, RED),
        _colour(colour, DIM),
        _colour(colour, BOLD),
        _colour(colour, RESET),
    )

    state = detect_tier(scenario["signals"])
    print(f"\n{b}{scenario['id']}  {scenario['name']}{x}")
    print(f"  {d}{scenario['narrative']}{x}")
    print(f"  signals   : {', '.join(scenario['signals']) or '(none)'}")
    print(f"  tier      : {state.tier.name}")
    print(f"  {d}{state.explain()}{x}")

    results = {}
    for claim in Claim:
        try:
            assert_claim_permitted(state, claim)
            print(f"    {g}PERMIT{x}  {claim.name:<16} {d}{claim.label}{x}")
            results[claim.name] = "permitted"
        except ClaimCeilingViolation:
            print(f"    {r}REFUSE{x}  {claim.name:<16} {d}{claim.label}{x}")
            results[claim.name] = "refused"

    if "previous_signals" in scenario:
        note = downgrade_note(detect_tier(scenario["previous_signals"]), state)
        if note:
            print(f"  {r}downgrade{x} : {note}")
        else:
            print(f"  {g}no downgrade{x} — fidelity stable or improving")

    print(f"  {d}why it matters: {scenario['why_it_matters']}{x}")
    return {"id": scenario["id"], "tier": state.tier.name, "claims": results}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--id", help="replay a single scenario by id, e.g. S05")
    ap.add_argument("--json", action="store_true", help="emit machine-readable output only")
    ap.add_argument("--no-colour", action="store_true")
    args = ap.parse_args()

    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    scenarios = data["scenarios"]
    if args.id:
        scenarios = [s for s in scenarios if s["id"].upper() == args.id.upper()]
        if not scenarios:
            print(f"no scenario with id {args.id}", file=sys.stderr)
            return 1

    if args.json:
        out = []
        for s in scenarios:
            state = detect_tier(s["signals"])
            out.append(
                {
                    "id": s["id"],
                    "name": s["name"],
                    **state.to_dict(),
                }
            )
        print(json.dumps(out, indent=2))
        return 0

    print(f"{BOLD}Fidelity ladder — scenario replay{RESET}")
    print(f"fixture: {FIXTURE.relative_to(REPO)}  (v{data['version']})")
    for s in scenarios:
        replay(s, colour=not args.no_colour)
    print(f"\n{len(scenarios)} scenario(s) replayed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
