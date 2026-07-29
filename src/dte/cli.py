"""Command-line interface for the Digital Twin Engine reference implementation.

Usage::

    dte simulate --patient-id demo-001 --hours 24 --seed 42
    dte risk --patient-index 0
    dte fairness --noise 2.5
    dte signals --artefact-rate 0.45

All output is derived from synthetic data. See ``DISCLAIMER.md``.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

import numpy as np

from dte import __version__
from dte.data.synthetic import generate_cohort, generate_day, generate_eeg, generate_rr_intervals
from dte.fairness.subgroup import evaluate_fairness
from dte.fusion.detector import FusionInput, OpportunityDetector
from dte.models.risk import RiskModel
from dte.policy.cue_selector import CueSelector, Response
from dte.signals.eeg import extract_eeg_features
from dte.signals.hrv import extract_hrv_features

BANNER = (
    "=" * 78
    + "\n  Dementia Digital Twin Engine — reference implementation v"
    + __version__
    + "\n  NOT A MEDICAL DEVICE.  ALL DATA SYNTHETIC.  ALL RESULTS ILLUSTRATIVE."
    + "\n  Read DISCLAIMER.md before citing anything below.\n"
    + "=" * 78
)


def cmd_simulate(args: argparse.Namespace) -> int:
    """Simulate a day of Memory Anchoring Pipeline decisions."""
    print(BANNER)
    print(f"\nMEMORY ANCHORING PIPELINE — simulated day for {args.patient_id}")
    print(f"seed={args.seed}  threshold=0.62  agitation veto=0.70  daily budget=8\n")

    detector = OpportunityDetector()
    selector = CueSelector(seed=args.seed)
    events = generate_day(seed=args.seed, n_events=max(4, args.hours // 2))
    rng = np.random.default_rng(args.seed)

    delivered = 0
    last_cue_min: Optional[float] = None
    distress_events = 0

    for e in events:
        now_min = e.hour * 60 + e.minute
        theta_z = float(rng.normal(1.0, 0.9))
        agitation = 0.82 if e.agitated else float(np.clip(rng.normal(0.25, 0.08), 0.0, 1.0))

        decision = detector.decide(
            FusionInput(
                place_class=e.place_class,
                place_significance=e.place_significance,
                hour_of_day=e.hour,
                agitation_index=agitation,
                theta_alpha_z=theta_z,
                eligible_content_count=e.eligible_content_count,
                signal_quality=0.82,
                minutes_since_last_cue=None if last_cue_min is None else now_min - last_cue_min,
                cues_delivered_today=delivered,
                consent_permits_cue=True,
            )
        )

        ts = f"[{e.hour:02d}:{e.minute:02d}]"
        print(
            f"{ts} place={e.place_class:<18} theta_z={theta_z:+.2f} agit={agitation:.2f} "
            f"content={e.eligible_content_count}"
        )
        print(f"          {decision.explain()}")

        if decision.deliver:
            selection = selector.select(e.place_class, e.hour)
            if selection is None:
                print("          all arms suppressed -> SILENT\n")
                continue
            latency = float(rng.uniform(1.1, 1.9))
            print(f"          {selection.explain()}")
            print(f"          delivered in {latency:.2f}s")

            roll = rng.random()
            if roll < 0.03:
                resp = Response.DISTRESSED
                distress_events += 1
            elif roll < 0.30:
                resp = Response.RECALLED
            elif roll < 0.65:
                resp = Response.ENGAGED
            elif roll < 0.85:
                resp = Response.IGNORED
            else:
                resp = Response.UNKNOWN

            reward = selector.update(selection, resp)
            rtxt = "MISSING (not imputed)" if reward is None else f"{reward:+.1f}"
            print(f"          response={resp.value} reward={rtxt}")
            if resp is Response.DISTRESSED:
                print(f"          ** {selection.arm.value} suppressed 24h; caregiver notified **")
            delivered += 1
            last_cue_min = now_min
        print()

    total = len(events)
    print("-" * 78)
    print(
        f"evaluations={total}  cues delivered={delivered}  silence rate={1 - delivered / total:.1%}"
    )
    print(f"distress events={distress_events} (benchmark B3.2 requires <= 1% of delivered cues)")
    print("\nLearned policy (per patient, never pooled):")
    print(json.dumps(selector.snapshot(), indent=2))
    print(
        "\nNOTE: silence is the majority outcome by design. The MAP is precision-weighted — "
        "built to miss\nopportunities rather than fire wrongly. A missed cue costs one moment; "
        "a wrong cue costs trust."
    )
    return 0


def cmd_risk(args: argparse.Namespace) -> int:
    """Score one synthetic patient, with reasoning."""
    print(BANNER)
    cohort = generate_cohort(n=600, seed=42)
    X, y, attributes = cohort.to_arrays()
    split = int(0.75 * len(y))
    model = RiskModel().fit(X[:split], y[:split], cohort.feature_names)

    y_pred = model.model.predict(X[split:])
    report = evaluate_fairness(y[split:], y_pred, {k: v[split:] for k, v in attributes.items()})
    model.max_subgroup_gap_at_release = report.max_gap
    proba = model.model.predict_proba(X[split:])[:, 1]
    model.brier_score = float(np.mean((proba - y[split:]) ** 2))

    p = cohort.patients[args.patient_index]
    risk = model.predict(p.features)

    print(f"\nRISK STRATIFICATION — {p.patient_id}")
    print(f"score={risk.score:.3f}  band={risk.band}  window={risk.window_months} months")
    print(f"ground truth (synthetic): converter={p.converter}\n")
    print("Ranked contributing features (a score cannot be issued without these — ADR-0006):")
    for i, f in enumerate(risk.top_features, 1):
        print(f"  {i}. {f.name:<28} {f.contribution:+.4f}  {f.direction:<16} {f.plain_language}")
    print(
        f"\nmodel={risk.model_version}  brier={risk.brier_score:.4f}  "
        f"max_subgroup_gap={risk.max_subgroup_gap_at_release}"
    )
    print(f"\nfairness gate: {report.summary()}")
    print("\nPATIENT-FACING SUMMARY:")
    print("  " + risk.patient_facing_summary().replace(". ", ".\n  "))
    return 0


def cmd_fairness(args: argparse.Namespace) -> int:
    """Run the subgroup fairness gate.

    Note on cohort size: the gate blocks when a subgroup has fewer than MIN_SUBGROUP_N samples,
    because "cannot certify" is treated as a failure (ADR-0007 rule 2). At small n the smallest
    subgroups are uncertifiable regardless of how fair the model is, so a small cohort will be
    blocked for that reason alone. Use --n to supply enough data for certification.
    """
    print(BANNER)
    print(f"\nSUBGROUP FAIRNESS GATE — n={args.n}, noise multiplier {args.noise}")
    print("(1.0 = fair cohort; higher = under-represented group is also noisier)\n")

    cohort = generate_cohort(n=args.n, underrepresented_noise_multiplier=args.noise, seed=42)
    X, y, attributes = cohort.to_arrays()
    split = int(0.75 * len(y))
    model = RiskModel().fit(X[:split], y[:split], cohort.feature_names)
    y_pred = model.model.predict(X[split:])
    report = evaluate_fairness(y[split:], y_pred, {k: v[split:] for k, v in attributes.items()})

    print(f"{'attribute':<20}{'group':<26}{'n':>5}{'acc':>9}{'sens':>9}{'certif':>9}")
    print("-" * 78)
    for s in report.subgroups:
        acc = f"{s.accuracy:.3f}" if s.accuracy is not None else "  -  "
        sens = f"{s.sensitivity:.3f}" if s.sensitivity is not None else "  -  "
        print(f"{s.attribute:<20}{s.group:<26}{s.n:>5}{acc:>9}{sens:>9}{str(s.certifiable):>9}")
    print("-" * 78)
    print(f"\n{report.summary()}")
    if report.blocking_reasons:
        print("\nBLOCKING REASONS:")
        for r in report.blocking_reasons:
            print(f"  - {r}")
        print("\nREMEDIATION:")
        for r in report.remediation:
            print(f"  - {r}")
    return 0 if report.passed else 1


def cmd_signals(args: argparse.Namespace) -> int:
    """Run the edge signal pipeline, demonstrating the quality gate."""
    print(BANNER)
    print(f"\nEDGE SIGNAL PIPELINE — artefact rate {args.artefact_rate}\n")

    raw, motion = generate_eeg(
        artefact_rate=args.artefact_rate, rng=np.random.default_rng(args.seed)
    )
    print(f"raw shape={raw.shape} (discarded after extraction — ADR-0002)")
    print(f"IMU-flagged epochs={int(motion.sum())}/{motion.size}\n")

    eeg = extract_eeg_features(raw, motion_mask=motion)
    print(
        f"quality={eeg.quality}  usable_epochs={eeg.usable_epoch_fraction:.1%}  "
        f"valid_channels={eeg.valid_channel_count}"
    )
    if eeg.is_usable:
        for band, v in eeg.relative_power.items():
            print(
                f"  {band:<6} relative power = {v:.4f}" if v is not None else f"  {band:<6} = n/a"
            )
        print(f"  theta/alpha ratio = {eeg.theta_alpha_ratio:.4f}")
    else:
        print("\n  ** QUALITY GATE FAILED — caller must NOT infer. **")
        print("  Features are excluded, never imputed. The clinician surface shows")
        print("  'insufficient data', not a score built on a guess (docs/05 §5.7).")

    hrv = extract_hrv_features(generate_rr_intervals(agitated=args.agitated))
    print(f"\nHRV quality={hrv.quality}")
    if hrv.is_usable:
        print(
            f"  rmssd={hrv.rmssd_ms:.1f}ms  lf/hf={hrv.lf_hf_ratio:.2f}  "
            f"agitation={hrv.agitation_index:.3f}"
        )
        if hrv.agitation_index > 0.70:
            print(
                "  ** AGITATION VETO ACTIVE — no cue may be delivered, regardless of confidence **"
            )
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dte",
        description="Dementia Digital Twin Engine reference implementation (synthetic data only).",
    )
    parser.add_argument("--version", action="version", version=f"dte {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sim = sub.add_parser("simulate", help="simulate a day of Memory Anchoring Pipeline decisions")
    p_sim.add_argument("--patient-id", default="demo-001")
    p_sim.add_argument("--hours", type=int, default=24)
    p_sim.add_argument("--seed", type=int, default=42)
    p_sim.set_defaults(func=cmd_simulate)

    p_risk = sub.add_parser("risk", help="score one synthetic patient with reasoning")
    p_risk.add_argument("--patient-index", type=int, default=0)
    p_risk.set_defaults(func=cmd_risk)

    p_fair = sub.add_parser("fairness", help="run the subgroup fairness gate")
    p_fair.add_argument("--noise", type=float, default=2.5)
    p_fair.add_argument(
        "--n",
        type=int,
        default=2000,
        help="cohort size; must be large enough that every subgroup reaches MIN_SUBGROUP_N",
    )
    p_fair.set_defaults(func=cmd_fairness)

    p_sig = sub.add_parser("signals", help="run the edge signal pipeline")
    p_sig.add_argument("--artefact-rate", type=float, default=0.15)
    p_sig.add_argument("--agitated", action="store_true")
    p_sig.add_argument("--seed", type=int, default=3)
    p_sig.set_defaults(func=cmd_signals)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
