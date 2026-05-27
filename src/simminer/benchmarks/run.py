"""Score the pipeline against synthetic ground truth encoded in filenames."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any

from ..examples import generate
from ..models import ComponentType
from ..pipeline import analyze

# filename encodings produced by the synthetic generator
_YS_RE = re.compile(r"ys_w(\d+)_a(\d+)_t(\d+)")
_MEEP_RE = re.compile(r"meep_ys_w(\d+)_a(\d+)_t(\d+)")
_DC_RE = re.compile(r"dc_gap(\d+)_L(\d+)")


def _truth_for(run_key: str) -> tuple[ComponentType, dict[str, float]] | None:
    """Recover (component, geometry params) ground truth from a run key."""
    name = run_key.rsplit("/", 1)[-1]
    if (m := _MEEP_RE.search(name)) or (m := _YS_RE.search(name)):
        w, a, t = (int(x) for x in m.groups())
        return ComponentType.Y_SPLITTER, {
            "width_nm": float(w), "branch_angle_deg": float(a), "taper_length_um": float(t),
        }
    if m := _DC_RE.search(name):
        g, L = (int(x) for x in m.groups())
        return ComponentType.DIRECTIONAL_COUPLER, {
            "gap_nm": float(g), "coupling_length_um": float(L),
        }
    return None


def run_benchmarks(root: str | Path | None = None) -> dict[str, Any]:
    """Generate (or reuse) a labeled repo and score the pipeline."""
    tmp = None
    if root is None:
        tmp = tempfile.mkdtemp(prefix="simminer-bench-")
        root = tmp
        generate(root, clean=True)
    result = analyze(root)

    cls_total = cls_correct = 0
    field_total = field_correct = 0
    for r in result.records:
        truth = _truth_for(r.run_key)
        if truth is None:
            continue  # noise / non-device run
        comp, params = truth
        cls_total += 1
        if r.component_type is comp:
            cls_correct += 1
        for key, expected in params.items():
            field_total += 1
            got = r.geometry.get(key)
            if isinstance(got, (int, float)) and abs(got - expected) <= max(1.0, 0.01 * expected):
                field_correct += 1

    d = result.discovery
    expected_dupes = 1  # generator plants exactly one byte-identical copy

    report = {
        "discovery": {
            "files_discovered": d.total_files,
            "logical_runs": len(d.run_keys),
            "duplicate_groups_found": len(d.duplicate_groups),
            "duplicate_detection_ok": len(d.duplicate_groups) == expected_dupes,
        },
        "classification": {
            "n": cls_total,
            "accuracy": round(cls_correct / cls_total, 4) if cls_total else 0.0,
        },
        "metadata_extraction": {
            "n_fields": field_total,
            "accuracy": round(field_correct / field_total, 4) if field_total else 0.0,
        },
    }
    return report
