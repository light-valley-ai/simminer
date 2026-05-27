"""Unit normalization helpers.

Photonics tools mix SI meters (Lumerical scripts), micrometers (layout), and
nanometers (feature sizes). simminer normalizes to a fixed convention:

* sub-micron feature sizes (width, gap, pitch, thickness, radius) -> nanometers
* device-scale lengths (taper / coupling / device length)        -> micrometers
* wavelengths                                                     -> nanometers

The conversion heuristics below infer the source unit from magnitude, which is
robust for realistic photonics values (a 500 nm waveguide is never 500 meters).
"""

from __future__ import annotations

SPEED_OF_LIGHT = 2.99792458e8  # m / s


def _infer_meters(value: float) -> float:
    """Return ``value`` expressed in meters, inferring the source unit.

    * |v| < 1e-3  -> already SI meters (e.g. 0.5e-6)
    * |v| < 100   -> micrometers       (e.g. 0.5, 20)
    * otherwise   -> nanometers        (e.g. 500, 1550)
    """
    a = abs(value)
    if a == 0:
        return 0.0
    if a < 1e-3:
        return value
    if a < 100:
        return value * 1e-6
    return value * 1e-9


def to_nm(value: float) -> float:
    """Normalize a length to nanometers."""
    return round(_infer_meters(value) * 1e9, 4)


def to_um(value: float) -> float:
    """Normalize a length to micrometers."""
    return round(_infer_meters(value) * 1e6, 6)


def freq_to_wavelength_nm(freq_hz: float) -> float:
    """Convert an optical frequency in Hz to vacuum wavelength in nm."""
    if freq_hz <= 0:
        return float("nan")
    return SPEED_OF_LIGHT / freq_hz * 1e9


def freq_unit_scale(unit: str) -> float:
    """Multiplier to convert a Touchstone frequency unit to Hz."""
    return {
        "HZ": 1.0,
        "KHZ": 1e3,
        "MHZ": 1e6,
        "GHZ": 1e9,
        "THZ": 1e12,
    }.get(unit.upper(), 1.0)
