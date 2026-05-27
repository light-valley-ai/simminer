"""Parser for Meep simulation outputs.

simminer recognizes two common Meep export shapes:

* a JSON sidecar carrying ``parameters`` and ``results`` dicts, and/or
* a flux CSV with a frequency/wavelength column and a flux/transmission column.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from . import units
from .lsf import _canonical_geometry  # reuse geometry alias resolution
from .sparam import _summarize_s21
from .tables import find_column, read_numeric_csv

_SIM_KEYS = {
    "resolution": "mesh_resolution",
    "wavelength": "wavelength_center_nm",
    "wvl": "wavelength_center_nm",
    "fcen": "fcen",
    "df": "df",
    "runtime": "runtime_s",
    "run_time": "runtime_s",
}


def parse_meep_json(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(errors="ignore")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"warnings": ["meep-json: invalid JSON"]}

    geometry: dict[str, Any] = {}
    simulation: dict[str, Any] = {"solver": "Meep"}
    results: dict[str, Any] = {}
    warnings: list[str] = []

    params = data.get("parameters", data.get("params", {}))
    if isinstance(params, dict):
        for k, v in params.items():
            if not isinstance(v, (int, float)):
                continue
            canon = _canonical_geometry(k, float(v))
            if canon:
                geometry.setdefault(canon[0], canon[1])
            elif k.lower() in _SIM_KEYS:
                key = _SIM_KEYS[k.lower()]
                simulation.setdefault(
                    key, units.to_nm(v) if key.endswith("_nm") else round(float(v), 6)
                )

    res = data.get("results", {})
    if isinstance(res, dict):
        for k, v in res.items():
            if isinstance(v, (int, float)):
                results.setdefault(k.lower(), round(float(v), 6))
    return {"geometry": geometry, "simulation": simulation, "results": results, "warnings": warnings}


def parse_meep_flux_csv(path: str | Path) -> dict[str, Any]:
    header, cols = read_numeric_csv(path)
    if not header:
        return {"results": {}, "warnings": ["meep-flux: empty"]}
    wl_col = find_column(header, "wavelength", "lambda", "wl")
    freq_col = find_column(header, "freq", "frequency", "fcen")
    flux_col = find_column(header, "flux", "transmission", "trans", "s21", "power")
    if flux_col is None or (wl_col is None and freq_col is None):
        return {"results": {}, "warnings": ["meep-flux: no recognizable columns"]}

    if wl_col is not None:
        wavelength_nm = [units.to_nm(v) if not math.isnan(v) else v for v in cols[wl_col]]
    else:
        # Meep frequencies are in units of 1/um (a=1um); convert via wavelength=1/f um
        wavelength_nm = [
            (1.0 / f) * 1000.0 if (not math.isnan(f) and f) else math.nan
            for f in cols[freq_col]
        ]

    raw = cols[flux_col]
    is_db = any((not math.isnan(v)) and v < 0 for v in raw)
    s21_db = raw if is_db else [
        10 * math.log10(v) if (not math.isnan(v) and v > 0) else math.nan for v in raw
    ]
    summary = _summarize_s21(wavelength_nm, s21_db)
    summary["result_kind"] = "meep_flux"
    return {"results": summary, "warnings": [] if summary.get("n_points") else ["meep-flux: no usable rows"]}
