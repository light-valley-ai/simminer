"""Parsers for S-parameter results: Touchstone ``.s2p`` and CSV exports."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from . import units
from .tables import find_column, read_numeric_csv


def _summarize_s21(wavelength_nm: list[float], s21_db: list[float]) -> dict[str, Any]:
    """Reduce an S21(λ) trace to scalar result metadata."""
    pairs = [
        (w, s) for w, s in zip(wavelength_nm, s21_db)
        if not (math.isnan(w) or math.isnan(s))
    ]
    if not pairs:
        return {}
    pairs.sort()
    wls = [p[0] for p in pairs]
    s21 = [p[1] for p in pairs]
    peak = max(s21)
    peak_wl = wls[s21.index(peak)]
    center_wl = 0.5 * (wls[0] + wls[-1])
    # nearest sample to band center
    s21_center = min(pairs, key=lambda p: abs(p[0] - center_wl))[1]
    out = {
        "n_points": len(pairs),
        "wavelength_start_nm": round(wls[0], 3),
        "wavelength_stop_nm": round(wls[-1], 3),
        "s21_peak_db": round(peak, 4),
        "s21_peak_wavelength_nm": round(peak_wl, 3),
        "s21_at_center_db": round(s21_center, 4),
        "insertion_loss_db": round(-peak, 4),
    }
    # 3 dB bandwidth around the peak (contiguous region within 3 dB of peak)
    thr = peak - 3.0
    in_band = [w for w, s in pairs if s >= thr]
    if len(in_band) >= 2:
        out["bandwidth_3db_nm"] = round(max(in_band) - min(in_band), 3)
    return out


def parse_touchstone(path: str | Path) -> dict[str, Any]:
    """Parse a 2-port Touchstone (``.s2p``) file.

    Touchstone v1 2-port data ordering is S11 S21 S12 S22. Supported formats:
    DB (dB/deg), MA (mag/deg), RI (real/imag).
    """
    freq_scale = 1.0
    fmt = "MA"
    freqs: list[float] = []
    s21_db: list[float] = []

    for line in Path(path).read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("!"):
            continue
        if line.startswith("#"):
            toks = line[1:].upper().split()
            if toks:
                freq_scale = units.freq_unit_scale(toks[0])
            for t in toks:
                if t in ("DB", "MA", "RI"):
                    fmt = t
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            continue
        freq_hz = nums[0] * freq_scale
        # S21 is the 2nd parameter pair: indices 3 and 4
        if len(nums) < 5:
            continue
        a, b = nums[3], nums[4]
        if fmt == "DB":
            mag_db = a
        elif fmt == "MA":
            mag_db = 20 * math.log10(a) if a > 0 else float("nan")
        else:  # RI
            mag = math.hypot(a, b)
            mag_db = 20 * math.log10(mag) if mag > 0 else float("nan")
        freqs.append(freq_hz)
        s21_db.append(mag_db)

    wavelength_nm = [units.freq_to_wavelength_nm(f) for f in freqs]
    summary = _summarize_s21(wavelength_nm, s21_db)
    summary["result_kind"] = "s_parameters"
    summary["source_format"] = f"touchstone/{fmt}"
    warnings = [] if summary.get("n_points") else ["s2p: no S21 data parsed"]
    return {"results": summary, "warnings": warnings}


def parse_sparam_csv(path: str | Path) -> dict[str, Any]:
    """Parse a CSV S-parameter export.

    Recognizes a wavelength/frequency column plus an S21 column (dB or linear).
    """
    header, cols = read_numeric_csv(path)
    if not header:
        return {"results": {}, "warnings": ["csv: empty or unparsable"]}

    wl_col = find_column(header, "wavelength", "lambda", "wl_nm", "wl")
    freq_col = find_column(header, "freq", "frequency")
    s21_col = find_column(header, "s21", "transmission", "s_21", "trans")
    if s21_col is None or (wl_col is None and freq_col is None):
        return {"results": {}, "warnings": ["csv: no recognizable S21 vs wavelength columns"]}

    if wl_col is not None:
        wavelength_nm = [units.to_nm(v) if not math.isnan(v) else v for v in cols[wl_col]]
    else:
        wavelength_nm = [units.freq_to_wavelength_nm(f) for f in cols[freq_col]]

    raw = cols[s21_col]
    is_db = "db" in s21_col or any((not math.isnan(v)) and v < 0 for v in raw)
    s21_db = raw if is_db else [
        10 * math.log10(v) if (not math.isnan(v) and v > 0) else float("nan") for v in raw
    ]

    summary = _summarize_s21(wavelength_nm, s21_db)
    summary["result_kind"] = "s_parameters"
    summary["source_format"] = "csv/db" if is_db else "csv/linear"
    warnings = [] if summary.get("n_points") else ["csv: no usable S21 samples"]
    return {"results": summary, "warnings": warnings}
