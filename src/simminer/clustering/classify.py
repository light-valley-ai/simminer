"""Heuristic component classification.

Phase-1 classifier combining two cheap, explainable signals:

1. **Filename / path keywords** -- engineers name folders and files after the
   device ("ysplitter_v1", "dc_gap0.2").
2. **Parameter fingerprints** -- the set of geometry parameters present is
   diagnostic (a branch angle implies a Y-splitter; a gap + coupling length
   implies a directional coupler).

A later phase can swap this for geometry-embedding similarity; the interface
(``classify_record``) stays the same.
"""

from __future__ import annotations

from ..models import ComponentType, SimulationRecord

# keyword -> (component, weight)
_KEYWORDS: dict[str, tuple[ComponentType, float]] = {
    "ysplit": (ComponentType.Y_SPLITTER, 3.0),
    "y_split": (ComponentType.Y_SPLITTER, 3.0),
    "y-split": (ComponentType.Y_SPLITTER, 3.0),
    "y_branch": (ComponentType.Y_SPLITTER, 3.0),
    "ybranch": (ComponentType.Y_SPLITTER, 2.5),
    "ebeam_y": (ComponentType.Y_SPLITTER, 3.0),
    "splitter": (ComponentType.Y_SPLITTER, 2.0),
    "mmi": (ComponentType.Y_SPLITTER, 1.0),
    "directional": (ComponentType.DIRECTIONAL_COUPLER, 3.0),
    "dircoupler": (ComponentType.DIRECTIONAL_COUPLER, 3.0),
    "ebeam_dc": (ComponentType.DIRECTIONAL_COUPLER, 3.0),
    "bdc": (ComponentType.DIRECTIONAL_COUPLER, 2.5),
    "contradc": (ComponentType.DIRECTIONAL_COUPLER, 2.5),
    "coupler": (ComponentType.DIRECTIONAL_COUPLER, 1.5),
    "_dc": (ComponentType.DIRECTIONAL_COUPLER, 2.0),
    "dc_": (ComponentType.DIRECTIONAL_COUPLER, 2.0),
    "halfring": (ComponentType.RING_RESONATOR, 3.5),
    "ring": (ComponentType.RING_RESONATOR, 3.0),
    "resonator": (ComponentType.RING_RESONATOR, 2.0),
    "grating": (ComponentType.GRATING_COUPLER, 3.0),
    "_gc": (ComponentType.GRATING_COUPLER, 2.0),
    "gc_": (ComponentType.GRATING_COUPLER, 2.0),
}


def _keyword_scores(text: str) -> dict[ComponentType, float]:
    text = text.lower()
    scores: dict[ComponentType, float] = {}
    for kw, (comp, w) in _KEYWORDS.items():
        if kw in text:
            scores[comp] = scores.get(comp, 0.0) + w
    return scores


def _param_scores(geometry: dict) -> dict[ComponentType, float]:
    scores: dict[ComponentType, float] = {}
    has = geometry.__contains__
    if has("branch_angle_deg"):
        scores[ComponentType.Y_SPLITTER] = scores.get(ComponentType.Y_SPLITTER, 0) + 3.0
    if has("taper_length_um") and not has("gap_nm"):
        scores[ComponentType.Y_SPLITTER] = scores.get(ComponentType.Y_SPLITTER, 0) + 1.0
    if has("gap_nm") and has("coupling_length_um"):
        scores[ComponentType.DIRECTIONAL_COUPLER] = scores.get(ComponentType.DIRECTIONAL_COUPLER, 0) + 3.0
    elif has("gap_nm"):
        scores[ComponentType.DIRECTIONAL_COUPLER] = scores.get(ComponentType.DIRECTIONAL_COUPLER, 0) + 1.5
    if has("bend_radius_um") and has("gap_nm"):
        scores[ComponentType.RING_RESONATOR] = scores.get(ComponentType.RING_RESONATOR, 0) + 2.0
    if has("grating_pitch_nm"):
        scores[ComponentType.GRATING_COUPLER] = scores.get(ComponentType.GRATING_COUPLER, 0) + 3.0
    return scores


def classify_record(record: SimulationRecord) -> tuple[ComponentType, float, str]:
    """Return ``(component_type, confidence, reason)`` for one run."""
    text = " ".join([record.run_key, *record.source_files])
    kw = _keyword_scores(text)
    pm = _param_scores(record.geometry)

    combined: dict[ComponentType, float] = {}
    for src in (kw, pm):
        for comp, val in src.items():
            combined[comp] = combined.get(comp, 0.0) + val

    if not combined:
        return ComponentType.UNKNOWN, 0.0, "no filename or parameter signal"

    best = max(combined, key=combined.get)
    total = sum(combined.values())
    confidence = round(combined[best] / total, 3) if total else 0.0
    reasons = []
    if best in kw:
        reasons.append("filename match")
    if best in pm:
        reasons.append("parameter fingerprint")
    reason = " + ".join(reasons) or "weak signal"
    return best, confidence, reason


def cluster_records(records: list[SimulationRecord]) -> dict[str, list[SimulationRecord]]:
    """Group classified records by component type (the cluster key)."""
    clusters: dict[str, list[SimulationRecord]] = {}
    for r in records:
        clusters.setdefault(r.component_type.value, []).append(r)
    return clusters
