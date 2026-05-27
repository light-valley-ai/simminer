"""Parser for transmission-spectrum CSV exports (monitor outputs)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from . import units
from .tables import find_column, read_numeric_csv


def parse_spectrum_csv(path: str | Path) -> dict[str, Any]:
    """Parse a wavelength vs. transmission spectrum CSV.

    Extracts peak/resonance wavelength, in/out band levels, and (for dips)
    the resonance and extinction useful for ring resonators.
    """
    header, cols = read_numeric_csv(path)
    if not header:
        return {"results": {}, "warnings": ["spectrum: empty or unparsable"]}

    wl_col = find_column(header, "wavelength", "lambda", "wl")
    t_col = find_column(header, "transmission", "power", "intensity", "_t", "trans", "magnitude")
    if wl_col is None or t_col is None:
        return {"results": {}, "warnings": ["spectrum: no wavelength/transmission columns"]}

    pairs = [
        (units.to_nm(w), t)
        for w, t in zip(cols[wl_col], cols[t_col])
        if not (math.isnan(w) or math.isnan(t))
    ]
    if not pairs:
        return {"results": {}, "warnings": ["spectrum: no numeric rows"]}

    pairs.sort()
    wls = [p[0] for p in pairs]
    ts = [p[1] for p in pairs]
    is_db = any(t < 0 for t in ts) or "db" in t_col

    peak_val = max(ts)
    dip_val = min(ts)
    peak_wl = wls[ts.index(peak_val)]
    dip_wl = wls[ts.index(dip_val)]

    summary: dict[str, Any] = {
        "result_kind": "spectrum",
        "n_points": len(pairs),
        "wavelength_start_nm": round(wls[0], 3),
        "wavelength_stop_nm": round(wls[-1], 3),
        "peak_wavelength_nm": round(peak_wl, 3),
        "resonance_wavelength_nm": round(dip_wl, 3),
        "units": "dB" if is_db else "linear",
    }
    summary["extinction_db"] = round(peak_val - dip_val, 4) if is_db else None
    return {"results": summary, "warnings": []}
