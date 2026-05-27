"""Extract geometry parameters encoded in file and directory names.

Real photonics archives encode the swept parameters directly in filenames, e.g.::

    dc_gap=200nm_Lc=10um.sparam
    ebeam_dc_halfring_straight_te1550_gap=80nm_radius=6um_width=520nm_thickness=210nm.dat
    Ybranch_Thickness =210 width=500.sparam

For ``.sparam``/``.dat`` files this is often the *only* source of geometry, so
filename parsing is a first-class extraction path (not just a classification
hint). Unlike the magnitude-inference used elsewhere, we honor an explicit unit
when present -- critical for values like ``gap=80nm`` (80 would otherwise look
like micrometers).
"""

from __future__ import annotations

import re
from typing import Any

from . import units
from .lsf import _GEOMETRY_ALIASES, _NM_FIELDS, _UM_FIELDS

# key = value [unit].  Handles "gap=200nm", "width=480", "Thickness =210", "Lc=10um".
_PARAM_RE = re.compile(
    r"([A-Za-z_]\w*)\s*=\s*(-?\d+(?:\.\d+)?)\s*(nm|um|µm|microns?|m)?",
    re.IGNORECASE,
)


def _field_for(key: str) -> str | None:
    low = key.lower()
    for field, aliases in _GEOMETRY_ALIASES.items():
        if low in aliases:
            return field
    return None


def _convert(field: str, value: float, unit: str) -> float:
    unit = unit.lower()
    if field in _NM_FIELDS:
        if unit == "nm":
            return round(value, 4)
        if unit in ("um", "µm", "micron", "microns"):
            return round(value * 1000.0, 4)
        if unit == "m":
            return round(value * 1e9, 4)
        return units.to_nm(value)  # no unit -> infer from magnitude
    if field in _UM_FIELDS:
        if unit in ("um", "µm", "micron", "microns"):
            return round(value, 6)
        if unit == "nm":
            return round(value / 1000.0, 6)
        if unit == "m":
            return round(value * 1e6, 6)
        return units.to_um(value)
    return round(value, 4)  # angles / dimensionless


def parse_params_from_name(name: str) -> dict[str, Any]:
    """Extract canonical geometry params from a file/dir name."""
    geometry: dict[str, Any] = {}
    for key, raw, unit in _PARAM_RE.findall(name):
        field = _field_for(key)
        if field is None:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        geometry.setdefault(field, _convert(field, value, unit))
    return geometry
