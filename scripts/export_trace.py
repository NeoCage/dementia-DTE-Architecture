"""Export one household's 90-day engine trace as JSON, for visualisation.

The point of this script is that the picture downstream is drawn from the engine's own
output rather than from a reimplementation of its rules. Anything a chart built on this
file shows — the tier at a given day, a claim that was refused, a baseline band the
current value sits outside — came out of ``TwinEngine.ingest``.

    PYTHONPATH=src python scripts/export_trace.py > trace.json

All data is synthetic. See DISCLAIMER.md.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

from dte.engine import Observation, TwinEngine
from dte.twin import ConsentSnapshot, TwinState

MILESTONES = {
    10: "phone sensing begins",
    14: "baseline establishes",
    30: "wristband issued",
    40: "EEG headband trial begins",
    55: "headband and wristband returned",
    70: "household goes dark",
    74: "contact re-established",
    80: "phone lost; gait still declining",
}


def build(days: int = 90, seed: int = 42) -> dict:
    twin = TwinState(
        patient_id="household-001",
        consent=ConsentSnapshot(
            location_data=True,
            wearable_physiology=True,
            neural_data=True,
            cue_delivery=True,
        ),
    )
    engine = TwinEngine(twin)
    start = datetime.now(timezone.utc) - timedelta(days=days)
    rng = np.random.default_rng(seed)
    frames = []

    for day in range(days):
        at = start + timedelta(days=day)
        if 70 <= day < 74:
            frames.append({"day": day, "dark": True, "event": MILESTONES.get(day)})
            continue

        phone = 10 <= day < 80
        band = 30 <= day < 55
        eeg = 40 <= day < 55
        gait = 1.10 if day < 60 else 1.10 - 0.035 * (day - 59)
        gait = round(gait + float(rng.normal(0, 0.012)), 4)

        result = engine.ingest(
            Observation(
                patient_id="household-001",
                at=at,
                caregiver_report={"mood": "settled"},
                phone_ambient={"gait_speed": gait} if phone else None,
                wristband={"hrv_rmssd": 34.0, "agitation_index": 0.2} if band else None,
                eeg={"theta_alpha_ratio": 1.4} if eeg else None,
                place_class="kitchen",
                place_significance=0.8,
                eligible_content_count=3,
                signal_quality=0.9,
            )
        )

        stat = twin.baseline.stats.get("gait_speed")
        frames.append(
            {
                "day": day,
                "dark": False,
                "event": MILESTONES.get(day),
                "tier": int(result.tier_state.tier),
                "available": sorted(result.tier_state.available),
                "downgrade": bool(result.downgrade),
                "stale": result.stale,
                "observations": twin.baseline.n_observations,
                "established": twin.baseline.is_established,
                "gait": gait if phone else None,
                "baseline_mean": round(stat.mean, 4) if stat else None,
                "baseline_sd": round(stat.std, 4) if stat else None,
                "deviation_z": (
                    round(z, 3) if (z := twin.deviation("gait_speed")) is not None else None
                ),
                "provenance": len(twin.provenance),
                "emissions": [e.claim.name for e in result.emissions],
                "suppressions": {s.claim.name: s.reason for s in result.suppressions},
            }
        )

    traj = twin.trajectory
    return {
        "patient_id": twin.patient_id,
        "days": days,
        "generated": datetime.now(timezone.utc).isoformat(),
        "synthetic": True,
        "frames": frames,
        "trajectory": None
        if traj is None
        else {
            "metric": traj.metric,
            "horizon_months": traj.horizon_months,
            "suppressed": traj.point_estimate_suppressed,
            "confidence": round(traj.confidence, 4),
            "projected": [round(v, 4) for v in traj.projected_values],
            "ci_lower": [round(v, 4) for v in traj.ci_lower],
            "ci_upper": [round(v, 4) for v in traj.ci_upper],
        },
    }


if __name__ == "__main__":
    json.dump(build(), sys.stdout, indent=1)
    sys.stdout.write("\n")
