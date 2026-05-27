"""Parser for Lumerical script files (``.lsf``).

Extracts geometry parameters and simulation setup from variable assignments and
``set(...)`` calls. This is a pragmatic regex/AST parser, not a full Lumerical
interpreter: it recognizes the common idioms found in real setup scripts.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from . import units

# variable assignment:  name = <expr> ;
_ASSIGN_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*([^;#]+);", re.MULTILINE)
# set("property", value)  /  setnamed("obj","property", value)
_SET_RE = re.compile(
    r"""set(?:named|global)?\s*\(\s*(?:["'][^"']*["']\s*,\s*)?["']([^"']+)["']\s*,\s*([^)]+)\)""",
    re.IGNORECASE,
)

# Canonical geometry field <- accepted source variable names (lowercased).
_GEOMETRY_ALIASES: dict[str, tuple[str, ...]] = {
    "width_nm": ("wg_width", "waveguide_width", "width", "w", "w_wg", "core_width"),
    "gap_nm": ("gap", "coupler_gap", "dc_gap", "g", "wg_gap"),
    "thickness_nm": ("wg_thickness", "thickness", "h", "wg_height", "height"),
    "branch_angle_deg": ("branch_angle", "splitter_angle", "angle", "theta"),
    "bend_radius_um": ("bend_radius", "radius", "r", "ring_radius"),
    "taper_length_um": ("taper_length", "taper_len", "l_taper", "taperlength"),
    "coupling_length_um": ("coupling_length", "coupler_length", "lc", "l_coupling", "l_c",
                           "couplelength", "couplinglength"),
    "device_length_um": ("device_length", "length", "l", "len", "l_device"),
    "grating_pitch_nm": ("grating_pitch", "pitch", "period", "lambda_grating"),
}
_NM_FIELDS = {"width_nm", "gap_nm", "thickness_nm", "grating_pitch_nm"}
_UM_FIELDS = {"bend_radius_um", "taper_length_um", "coupling_length_um", "device_length_um"}

# set("...") property -> canonical simulation field (value, scale handled below).
_SOLVER_ADD = {
    "addfdtd": "FDTD",
    "addvarfdtd": "varFDTD",
    "addeme": "EME",
    "addmode": "FDE",
    "addmesh": None,
}


def _safe_number(expr: str) -> float | None:
    """Evaluate a numeric RHS supporting literals and ``*`` / ``/`` of literals."""
    expr = expr.strip()
    try:
        node = ast.parse(expr, mode="eval").body
    except SyntaxError:
        return None

    def ev(n: ast.AST) -> float:
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Mult, ast.Div, ast.Add, ast.Sub)):
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Mult):
                return a * b
            if isinstance(n.op, ast.Div):
                return a / b if b else float("nan")
            if isinstance(n.op, ast.Add):
                return a + b
            return a - b
        raise ValueError("non-numeric")

    try:
        return ev(node)
    except (ValueError, ZeroDivisionError, TypeError):
        return None


def _canonical_geometry(name: str, value: float) -> tuple[str, float] | None:
    low = name.lower()
    for field, aliases in _GEOMETRY_ALIASES.items():
        if low in aliases:
            if field in _NM_FIELDS:
                return field, units.to_nm(value)
            if field in _UM_FIELDS:
                return field, units.to_um(value)
            return field, round(value, 4)  # angles, dimensionless
    return None


def parse_lsf(path: str | Path) -> dict[str, Any]:
    """Parse a Lumerical script into ``{geometry, simulation, warnings}``."""
    text = Path(path).read_text(errors="ignore")
    geometry: dict[str, Any] = {}
    simulation: dict[str, Any] = {}
    warnings: list[str] = []
    raw_vars: dict[str, float] = {}

    for name, rhs in _ASSIGN_RE.findall(text):
        val = _safe_number(rhs)
        if val is None:
            continue
        raw_vars[name.lower()] = val
        canon = _canonical_geometry(name, val)
        if canon:
            geometry.setdefault(canon[0], canon[1])

    for prop, rhs in _SET_RE.findall(text):
        val = _safe_number(rhs)
        if val is None:
            continue
        key = prop.strip().lower()
        if "wavelength" in key or "lambda" in key:
            field = (
                "wavelength_start_nm" if "start" in key
                else "wavelength_stop_nm" if "stop" in key
                else "wavelength_center_nm"
            )
            simulation.setdefault(field, units.to_nm(val))
        elif "mesh accuracy" in key:
            simulation.setdefault("mesh_accuracy", round(val))
        elif key in ("dx", "dy", "dz", "mesh size", "min mesh step"):
            simulation.setdefault("mesh_size_nm", units.to_nm(val))

    low_text = text.lower()
    for fn, solver in _SOLVER_ADD.items():
        if fn in low_text and solver:
            simulation.setdefault("solver", solver)
            break

    if "pml" in low_text:
        simulation.setdefault("boundary_conditions", "PML")

    if not geometry:
        warnings.append("lsf: no geometry parameters recognized")

    return {"geometry": geometry, "simulation": simulation, "warnings": warnings}
