"""The agitation veto: a cue is blocked even at maximal confidence.

This is the central safety asymmetry of the Memory Anchoring Pipeline. Physiology does not lower
the confidence score where a strong neural signal could outvote it — it blocks delivery outright.

Run: PYTHONPATH=src python examples/01_agitation_veto.py
"""

from dte.fusion.detector import FusionInput, OpportunityDetector


def scenario(label: str, **kw) -> None:
    detector = OpportunityDetector()
    base = dict(
        place_class="known-significant",
        place_significance=1.0,
        hour_of_day=14,
        agitation_index=0.20,
        theta_alpha_z=3.0,
        eligible_content_count=10,
        signal_quality=1.0,
        minutes_since_last_cue=120.0,
        cues_delivered_today=0,
        consent_permits_cue=True,
    )
    base.update(kw)
    d = detector.decide(FusionInput(**base))
    verdict = "DELIVER" if d.deliver else "SILENT"
    print(f"{label:<44} conf={d.confidence:.3f} tau={d.threshold:.2f}  -> {verdict}")
    if not d.deliver:
        print(f"{'':<44} reason: {d.reason}")


print(__doc__.splitlines()[0])
print("=" * 88)
print("\nBest-case conditions, calm patient:")
scenario("calm (agitation 0.20)")

print("\nIdentical conditions except agitation — note confidence is UNCHANGED and still above tau:")
scenario("agitated (agitation 0.75)", agitation_index=0.75)
scenario("highly agitated (agitation 0.95)", agitation_index=0.95)
scenario("agitation unknown (fails closed)", agitation_index=None)

print("\n" + "=" * 88)
print("""
The confidence score is identical in every case above. A weighted-vote design would have fired in
all of them, because the neural and context channels are maximal. The veto is what prevents that.

Rationale: a cue delivered to an agitated person is not merely ineffective. It is likely to be
actively distressing, and to teach the person to resent the device. The architecture treats
"make it worse" as a categorically different error from "miss an opportunity".

  docs/03-digital-twin-engine.md  §3.3
  docs/04-memory-anchoring-pipeline.md  §4.4
""")
