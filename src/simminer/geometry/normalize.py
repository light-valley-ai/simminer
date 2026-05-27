"""Geometry consolidation and feature-vector extraction."""

from __future__ import annotations

from typing import Any

# Canonical numeric geometry fields, in a stable order. Used as the feature
# space for clustering, coverage analysis, and dataset columns.
GEOMETRY_FIELDS: tuple[str, ...] = (
    "width_nm",
    "gap_nm",
    "thickness_nm",
    "branch_angle_deg",
    "bend_radius_um",
    "taper_length_um",
    "coupling_length_um",
    "device_length_um",
    "grating_pitch_nm",
)


def normalize(geometry: dict[str, Any]) -> dict[str, Any]:
    """Return a cleaned geometry dict.

    Drops null values, rounds floats, and preserves any non-canonical extras
    (e.g. ``polygon_count``, ``bbox_width_um``) so nothing is silently lost.
    """
    out: dict[str, Any] = {}
    for k, v in geometry.items():
        if v is None:
            continue
        out[k] = round(v, 4) if isinstance(v, float) else v
    return out


def feature_vector(geometry: dict[str, Any]) -> dict[str, float]:
    """Extract the numeric geometry features present in ``geometry``."""
    return {
        f: float(geometry[f])
        for f in GEOMETRY_FIELDS
        if isinstance(geometry.get(f), (int, float))
    }
