"""Multimodal fusion and opportunity detection. Implements docs/04-memory-anchoring-pipeline.md."""

from dte.fusion.detector import (
    AlertBudget,
    FusionInput,
    GateResult,
    OpportunityDecision,
    OpportunityDetector,
)

__all__ = ["AlertBudget", "FusionInput", "GateResult", "OpportunityDecision", "OpportunityDetector"]
