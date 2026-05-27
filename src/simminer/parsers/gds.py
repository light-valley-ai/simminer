"""Minimal, dependency-free GDSII reader/writer.

Only the subset of GDSII needed to mine geometry is implemented: BOUNDARY
elements with LAYER/DATATYPE/XY. This is enough to recover polygon counts,
layers, bounding box, and a stable geometry hash for validation -- without
pulling in ``gdstk``/``gdspy`` (which may lack wheels on new Pythons).
"""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any

# --- GDSII REAL8 (8-byte excess-64 base-16 float) -------------------------------

def _encode_real8(value: float) -> bytes:
    if value == 0:
        return b"\x00" * 8
    sign = 0
    if value < 0:
        sign = 0x80
        value = -value
    exp = 0
    while value >= 1:
        value /= 16.0
        exp += 1
    while value < 1 / 16.0:
        value *= 16.0
        exp -= 1
    mant = int(round(value * (1 << 56)))
    if mant == (1 << 56):
        mant >>= 4
        exp += 1
    return bytes([sign | (exp + 64)]) + mant.to_bytes(7, "big")


def _decode_real8(b: bytes) -> float:
    sign = -1.0 if b[0] & 0x80 else 1.0
    exp = (b[0] & 0x7F) - 64
    mant = int.from_bytes(b[1:], "big") / (1 << 56)
    return sign * mant * 16.0 ** exp


# --- record helpers -------------------------------------------------------------

def _record(rtype: int, dtype: int, payload: bytes = b"") -> bytes:
    length = 4 + len(payload)
    return struct.pack(">HBB", length, rtype, dtype) + payload


def write_gds(
    path: str | Path,
    polygons: list[list[tuple[float, float]]],
    *,
    libname: str = "SIMMINER",
    cellname: str = "TOP",
    layer: int = 1,
    db_unit_m: float = 1e-9,
    user_unit_m: float = 1e-6,
) -> None:
    """Write polygons (coordinates in micrometers) to a minimal GDSII file."""
    scale = user_unit_m / db_unit_m  # um -> db units
    out = bytearray()
    out += _record(0x00, 0x02, struct.pack(">h", 600))            # HEADER v6
    out += _record(0x01, 0x02, struct.pack(">12h", *([0] * 12)))  # BGNLIB
    out += _record(0x02, 0x06, libname.encode().ljust(2, b"\x00"))  # LIBNAME
    out += _record(0x03, 0x05, _encode_real8(user_unit_m / db_unit_m) + _encode_real8(db_unit_m))  # UNITS
    out += _record(0x05, 0x02, struct.pack(">12h", *([0] * 12)))  # BGNSTR
    name = cellname.encode()
    if len(name) % 2:
        name += b"\x00"
    out += _record(0x06, 0x06, name)                              # STRNAME
    for poly in polygons:
        pts = list(poly)
        if pts and pts[0] != pts[-1]:
            pts = pts + [pts[0]]  # GDSII boundaries are closed
        out += _record(0x08, 0x00)                                # BOUNDARY
        out += _record(0x0D, 0x02, struct.pack(">h", layer))      # LAYER
        out += _record(0x0E, 0x02, struct.pack(">h", 0))          # DATATYPE
        coords = bytearray()
        for x, y in pts:
            coords += struct.pack(">ii", int(round(x * scale)), int(round(y * scale)))
        out += _record(0x10, 0x03, bytes(coords))                 # XY
        out += _record(0x11, 0x00)                                # ENDEL
    out += _record(0x07, 0x00)                                    # ENDSTR
    out += _record(0x04, 0x00)                                    # ENDLIB
    Path(path).write_bytes(bytes(out))


def read_gds(path: str | Path) -> dict[str, Any]:
    """Read a GDSII file and summarize its geometry."""
    data = Path(path).read_bytes()
    pos = 0
    db_unit_m = 1e-9
    polygons: list[list[tuple[int, int]]] = []
    layers: set[int] = set()
    cur_layer = 0
    cur_xy: list[tuple[int, int]] | None = None
    warnings: list[str] = []

    while pos + 4 <= len(data):
        (length, rtype, dtype) = struct.unpack(">HBB", data[pos:pos + 4])
        if length < 4:
            warnings.append("gds: malformed record length")
            break
        payload = data[pos + 4:pos + length]
        pos += length
        if rtype == 0x03:  # UNITS
            if len(payload) >= 16:
                db_unit_m = _decode_real8(payload[8:16])
        elif rtype == 0x08:  # BOUNDARY
            cur_xy = []
        elif rtype == 0x0D:  # LAYER
            cur_layer = struct.unpack(">h", payload[:2])[0]
        elif rtype == 0x10 and cur_xy is not None:  # XY
            n = len(payload) // 8
            vals = struct.unpack(f">{2 * n}i", payload[:8 * n])
            cur_xy = [(vals[i], vals[i + 1]) for i in range(0, len(vals), 2)]
        elif rtype == 0x11:  # ENDEL
            if cur_xy:
                polygons.append(cur_xy)
                layers.add(cur_layer)
            cur_xy = None
        elif rtype == 0x04:  # ENDLIB
            break

    geometry: dict[str, Any] = {"polygon_count": len(polygons), "layers": sorted(layers)}
    if polygons:
        xs = [p[0] for poly in polygons for p in poly]
        ys = [p[1] for poly in polygons for p in poly]
        # coordinates are in db units; convert to um
        to_um = db_unit_m / 1e-6
        geometry["bbox_width_um"] = round((max(xs) - min(xs)) * to_um, 4)
        geometry["bbox_height_um"] = round((max(ys) - min(ys)) * to_um, 4)
        geometry["geometry_hash"] = geometry_hash(polygons)
    else:
        warnings.append("gds: no polygons found")
    return {"geometry": geometry, "warnings": warnings}


def geometry_hash(polygons: list[list[tuple[int, int]]]) -> str:
    """Stable hash of polygon geometry, invariant to polygon ordering."""
    norm = sorted(tuple(tuple(pt) for pt in poly) for poly in polygons)
    h = hashlib.sha256(repr(norm).encode())
    return h.hexdigest()[:16]
