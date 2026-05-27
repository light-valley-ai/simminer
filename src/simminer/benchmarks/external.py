"""Validate the pipeline against a real external PDK (Tier 2).

Designed for the open SiEPIC EBeam PDK, whose component folders give ground-truth
labels and whose ``.sparam``/``.dat`` files are real Lumerical S-parameters.

Three independent signals, none circular:

* **discovery**  -- what gets recognized, and how much is mirrored (duplicates).
* **classification** -- predicted component vs. folder-derived truth, on the
  unambiguous families we target (Y-branch, directional coupler, grating coupler).
* **parser fidelity** -- a *physics* check on the parsed S-parameters: a passive
  device cannot have |S21| > 0 dB, and a Y-branch should split ~3 dB per arm. If
  our amplitude->dB conversion were wrong, these would fail. This validates the
  parser independently of any filename metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import ComponentType
from ..pipeline import analyze


def _expected_component(run_key: str) -> ComponentType | None:
    """Folder/name-derived ground truth for unambiguous families (else None)."""
    k = run_key.lower()
    if "halfring" in k or "contradc" in k or "cdc" in k:
        return None  # ring/contra-DC hybrids: not scored for accuracy
    if "y_branch" in k or "ybranch" in k or "ebeam_y" in k:
        return ComponentType.Y_SPLITTER
    if "ebeam_dc" in k or "/dc_" in k or "bdc" in k:
        return ComponentType.DIRECTIONAL_COUPLER
    if "gc_" in k or "/gc" in k or "grating" in k:
        return ComponentType.GRATING_COUPLER
    return None


def run_external(root: str | Path) -> dict[str, Any]:
    """Run the pipeline over a real PDK tree and score it."""
    result = analyze(root)
    d = result.discovery

    # --- classification accuracy on labeled families ---
    scored = correct = 0
    confusion: dict[str, dict[str, int]] = {}
    for r in result.records:
        expected = _expected_component(r.run_key)
        if expected is None:
            continue
        scored += 1
        got = r.component_type
        confusion.setdefault(expected.value, {}).setdefault(got.value, 0)
        confusion[expected.value][got.value] += 1
        if got is expected:
            correct += 1

    # --- parser fidelity: physics checks on parsed S-parameters ---
    sparam_recs = [
        r for r in result.records
        if r.results.get("source_format") == "interconnect"
        and isinstance(r.results.get("s21_peak_db"), (int, float))
    ]
    passivity_ok = sum(1 for r in sparam_recs if r.results["s21_peak_db"] <= 0.1)
    yb = [
        r for r in sparam_recs
        if r.component_type is ComponentType.Y_SPLITTER
        and isinstance(r.results.get("insertion_loss_db"), (int, float))
    ]
    yb_il = [r.results["insertion_loss_db"] for r in yb]
    yb_within = sum(1 for il in yb_il if 2.5 <= il <= 5.0)

    # --- GDS reader on real layouts ---
    gds_recs = [r for r in result.records if any(f.endswith(".gds") for f in r.source_files)]
    gds_with_polys = sum(1 for r in gds_recs if r.geometry.get("polygon_count", 0) > 0)

    def rate(num: int, den: int) -> float:
        return round(num / den, 4) if den else 0.0

    return {
        "root": str(root),
        "discovery": {
            "files_discovered": d.total_files,
            "logical_runs": len(d.run_keys),
            "duplicate_groups": len(d.duplicate_groups),
            "counts_by_filetype": d.counts_by_type(),
        },
        "classification": {
            "n_scored": scored,
            "accuracy": rate(correct, scored),
            "confusion": confusion,
            "component_counts": result.component_counts(),
        },
        "parser_fidelity": {
            "n_sparam_records": len(sparam_recs),
            "passivity_ok_rate": rate(passivity_ok, len(sparam_recs)),
            "ybranch_n": len(yb_il),
            "ybranch_insertion_loss_mean_db": round(sum(yb_il) / len(yb_il), 3) if yb_il else None,
            "ybranch_within_3db_rate": rate(yb_within, len(yb_il)),
            "gds_records": len(gds_recs),
            "gds_with_polygons_rate": rate(gds_with_polys, len(gds_recs)),
        },
    }
