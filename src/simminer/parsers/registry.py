"""Dispatch a discovered file to the appropriate parser.

Each parser returns a partial metadata dict with any of the keys
``geometry`` / ``simulation`` / ``results`` / ``warnings``. The pipeline merges
these across all files of a run into one :class:`SimulationRecord`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .interconnect import parse_interconnect
from .lsf import _canonical_geometry, parse_lsf
from .meep import parse_meep_flux_csv, parse_meep_json
from .sparam import parse_sparam_csv, parse_touchstone
from .spectra import parse_spectrum_csv
from . import gds


def _peek(path: Path, n: int = 8192) -> str:
    try:
        return path.read_text(errors="ignore")[:n].lower()
    except OSError:
        return ""


def _parse_geometry_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return {"warnings": ["json: invalid"]}
    geometry: dict[str, Any] = {}
    # parametric form: flat dict of named dimensions
    src = data.get("parameters", data) if isinstance(data, dict) else {}
    if isinstance(src, dict):
        for k, v in src.items():
            if isinstance(v, (int, float)):
                canon = _canonical_geometry(k, float(v))
                if canon:
                    geometry.setdefault(canon[0], canon[1])
    # polygonal form: list of polygons / coordinate arrays
    polys = None
    if isinstance(data, dict):
        polys = data.get("polygons") or data.get("coordinates")
    if isinstance(polys, list) and polys:
        geometry["polygon_count"] = len(polys)
        try:
            pts = [tuple(pt) for poly in polys for pt in poly]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            geometry["bbox_width_um"] = round(max(xs) - min(xs), 4)
            geometry["bbox_height_um"] = round(max(ys) - min(ys), 4)
        except (TypeError, IndexError, ValueError):
            pass
    return {"geometry": geometry, "warnings": [] if geometry else ["json: no geometry recognized"]}


def parse_file(path: str | Path) -> dict[str, Any]:
    """Parse one file, returning partial metadata (never raises on bad content)."""
    path = Path(path)
    ext = path.suffix.lower().lstrip(".")

    try:
        if ext in ("lsf", "lms"):
            return parse_lsf(path)
        if ext == "ctl":  # Meep scheme control file: shallow marker only
            return {"simulation": {"solver": "Meep"}, "warnings": ["ctl: not deeply parsed"]}
        if ext in ("s2p", "s4p"):
            return parse_touchstone(path)
        if ext == "sparam":
            return parse_interconnect(path)
        if ext in ("gds", "gdsii"):
            return gds.read_gds(path)
        if ext == "dat":
            # INTERCONNECT S-params start with a "(...,'transmission')" header;
            # otherwise treat as a whitespace/CSV spectrum.
            head = _peek(path, 256)
            if "transmission" in head and head.lstrip().startswith("("):
                return parse_interconnect(path)
            return parse_spectrum_csv(path)
        if ext == "csv":
            head = _peek(path, 512)
            if "s21" in head or "s_21" in head:
                return parse_sparam_csv(path)
            if "flux" in head:
                return parse_meep_flux_csv(path)
            return parse_spectrum_csv(path)
        if ext == "json":
            head = _peek(path, 2048)
            if "meep" in head or "fcen" in head or '"results"' in head:
                return parse_meep_json(path)
            return _parse_geometry_json(path)
        if ext in ("fsp", "h5", "hdf5", "mat", "npz", "oas"):
            # binary solver/layout containers: recognized but not parsed in MVP
            return {"warnings": [f"{ext}: binary format, not parsed in MVP"]}
        if ext == "txt":
            return parse_spectrum_csv(path)
    except Exception as exc:  # parsers must never crash discovery
        return {"warnings": [f"{ext}: parse error: {exc}"]}
    return {"warnings": [f"{ext}: no parser"]}
