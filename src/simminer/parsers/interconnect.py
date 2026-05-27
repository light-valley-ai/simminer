"""Parser for the Lumerical INTERCONNECT S-parameter format (``.sparam`` / ``.dat``).

This is the format shipped by the SiEPIC EBeam PDK and emitted by Lumerical's
S-parameter sweep utility. A file is a sequence of per-port-pair blocks::

    ('port 2','TE',1,'port 1',1,'transmission')   # (out, mode, mid_out, in, mid_in, type)
    (51,3)                                         # rows, cols
    1.8737e+014  0.0105154  2.7804                 # freq[Hz]  |S|(linear)  phase[rad]
    ...

The header may carry an optional 7th element (group delay), which we ignore.
We reduce the full S-matrix to the primary transmission path (the off-diagonal,
fundamental-mode block with the largest peak) and summarize it like any other
S21 trace.
"""

from __future__ import annotations

import ast
import math
from pathlib import Path
from typing import Any

from . import units
from .sparam import _summarize_s21


def _parse_blocks(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    blocks: list[dict[str, Any]] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i].strip()
        if line.startswith("(") and "transmission" in line.lower():
            try:
                header = ast.literal_eval(line)
            except (ValueError, SyntaxError):
                i += 1
                continue
            out_port, mode_label, mode_id_out, in_port = header[0], header[1], header[2], header[3]
            i += 1
            while i < n and not lines[i].strip():
                i += 1
            if i >= n:
                break
            dims = lines[i].strip()
            try:
                nrows = ast.literal_eval(dims)[0] if dims.startswith("(") else int(dims.split()[0])
            except (ValueError, SyntaxError, IndexError):
                i += 1
                continue
            i += 1
            rows: list[tuple[float, float, float]] = []
            while i < n and len(rows) < nrows:
                parts = lines[i].split()
                if len(parts) >= 3:
                    try:
                        rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
                    except ValueError:
                        pass
                i += 1
            blocks.append({
                "out": str(out_port), "in": str(in_port),
                "mode": str(mode_label), "mode_id": mode_id_out, "rows": rows,
            })
        else:
            i += 1
    return blocks


def _is_fundamental(block: dict[str, Any]) -> bool:
    return "te" in block["mode"].lower() or block["mode_id"] in (1, "1")


def parse_interconnect(path: str | Path) -> dict[str, Any]:
    """Parse an INTERCONNECT S-parameter file into result metadata."""
    blocks = _parse_blocks(Path(path).read_text(errors="ignore"))
    if not blocks:
        return {"results": {}, "warnings": ["interconnect: no S-parameter blocks parsed"]}

    ports = sorted({b["in"] for b in blocks} | {b["out"] for b in blocks})
    modes = sorted({b["mode"] for b in blocks})

    # primary transmission = off-diagonal, fundamental mode, largest peak amplitude
    def peak_amp(b: dict[str, Any]) -> float:
        return max((r[1] for r in b["rows"]), default=0.0)

    candidates = [b for b in blocks if b["in"] != b["out"] and b["rows"]]
    fundamental = [b for b in candidates if _is_fundamental(b)] or candidates
    if not fundamental:
        return {"results": {"n_ports": len(ports), "n_modes": len(modes)},
                "warnings": ["interconnect: no transmission path found"]}
    primary = max(fundamental, key=peak_amp)

    wavelength_nm = [units.freq_to_wavelength_nm(r[0]) for r in primary["rows"]]
    s21_db = [20 * math.log10(r[1]) if r[1] > 0 else float("nan") for r in primary["rows"]]

    summary = _summarize_s21(wavelength_nm, s21_db)
    summary.update({
        "result_kind": "s_parameters",
        "source_format": "interconnect",
        "n_ports": len(ports),
        "n_modes": len(modes),
        "primary_path": f"{primary['in']}->{primary['out']}",
    })
    return {"results": summary, "warnings": [] if summary.get("n_points") else ["interconnect: empty trace"]}
