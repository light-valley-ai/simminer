"""Generate a realistic synthetic photonics simulation repository.

The data is physically *plausible* (not solver-accurate): toy analytic models
give monotonic, parameter-dependent outputs so that classification, dataset
building, and readiness scoring exercise the same code paths real data would.

Layout produced::

    <root>/
      ysplitter_v1/            Lumerical .lsf + CSV S-params + spectra + .gds
      directional_coupler/     Lumerical .lsf + Touchstone .s2p
      sweeps/meep/             Meep JSON + flux CSV runs
      exports/notes.txt        noise / non-artifact files
      <duplicate file>         byte-identical copy (duplicate detection)
"""

from __future__ import annotations

import json
import math
import random
import shutil
from pathlib import Path

from ..parsers import gds
from ..parsers.units import SPEED_OF_LIGHT

# parameter sweep grids (a few combinations dropped to leave coverage gaps)
_YS_WIDTHS = (450, 500, 550)        # nm
_YS_ANGLES = (8, 10, 12, 15)        # deg
_YS_TAPERS = (10, 15, 20)           # um
_DC_GAPS = (150, 200, 250, 300, 350)      # nm
_DC_LENGTHS = (10, 15, 20, 25, 30, 35)    # um


def _ys_loss_db(width_nm: float, angle_deg: float, taper_um: float, wl_nm: float) -> float:
    """Per-branch transmission of a Y-splitter (ideal -3.01 dB minus excess)."""
    excess = 0.05 + 0.012 * (angle_deg - 8) ** 1.3 + 0.004 * abs(taper_um - 18)
    # signed width term so distinct widths give distinct outputs (no accidental dupes)
    excess += 0.003 * (width_nm - 500) / 10.0
    slope = -0.0008 * (wl_nm - 1550)
    return -3.01 - excess + slope


def _dc_through_db(gap_nm: float, length_um: float, wl_nm: float) -> float:
    """Through-port (S21) transmission of a directional coupler."""
    kappa = 0.18 * math.exp(-(gap_nm - 150) / 120.0)  # 1/um
    kappa *= 1.0 + 0.0006 * (wl_nm - 1550)            # mild dispersion
    through = math.cos(kappa * length_um) ** 2
    through = max(through, 1e-4)
    return 10 * math.log10(through) - 0.1             # 0.1 dB excess loss


def _write_lsf(path: Path, kind: str, params: dict[str, float]) -> None:
    lines = [f"# {kind} FDTD setup (synthetic)", "newproject;", "addfdtd;"]
    if kind == "y_splitter":
        lines += [
            f"wg_width = {params['width_nm'] * 1e-9:.4e};",
            f"branch_angle = {params['angle_deg']};",
            f"taper_length = {params['taper_um'] * 1e-6:.4e};",
            "wg_thickness = 220e-9;",
        ]
    else:
        lines += [
            f"wg_width = {params['width_nm'] * 1e-9:.4e};",
            f"coupler_gap = {params['gap_nm'] * 1e-9:.4e};",
            f"coupling_length = {params['length_um'] * 1e-6:.4e};",
            "wg_thickness = 220e-9;",
        ]
    lines += [
        'set("mesh accuracy", 3);',
        'set("wavelength start", 1.5e-6);',
        'set("wavelength stop", 1.6e-6);',
        'set("boundary conditions", "PML");',
        "run;",
    ]
    path.write_text("\n".join(lines) + "\n")


def _write_ys_results(base: Path, p: dict[str, float]) -> None:
    wls = [1500 + i * 2 for i in range(51)]  # 1500..1600 nm
    # spectrum CSV
    spec = ["wavelength_nm,transmission_db"]
    for wl in wls:
        spec.append(f"{wl},{_ys_loss_db(p['width_nm'], p['angle_deg'], p['taper_um'], wl):.4f}")
    base.with_name(base.name + "_spectrum").with_suffix(".csv").write_text("\n".join(spec) + "\n")
    # S-parameter CSV
    sp = ["wavelength_nm,S21_dB,S21_deg,S11_dB"]
    for wl in wls:
        s21 = _ys_loss_db(p["width_nm"], p["angle_deg"], p["taper_um"], wl)
        sp.append(f"{wl},{s21:.4f},{(wl % 360) - 180:.2f},-26.5")
    base.with_name(base.name + "_sparams").with_suffix(".csv").write_text("\n".join(sp) + "\n")


def _write_ys_gds(path: Path, p: dict[str, float]) -> None:
    w = p["width_nm"] / 1000.0  # um
    t = p["taper_um"]
    half = math.tan(math.radians(p["angle_deg"])) * t + w
    polys = [
        [(0, -w / 2), (5, -w / 2), (5, w / 2), (0, w / 2)],                 # input wg
        [(5, -w / 2), (5 + t, -half), (5 + t, -half + w), (5, w / 2)],      # lower branch
        [(5, -w / 2), (5 + t, half - w), (5 + t, half), (5, w / 2)],        # upper branch
    ]
    gds.write_gds(path, polys, cellname="YSPLITTER", layer=1)


def _write_dc_s2p(path: Path, p: dict[str, float]) -> None:
    wls = [1520 + i * 1.5 for i in range(41)]  # 1520..1580 nm
    lines = [
        "! Synthetic directional coupler S-parameters",
        f"! gap={p['gap_nm']}nm coupling_length={p['length_um']}um",
        "# HZ S DB R 50",
    ]
    for wl in wls:
        freq = SPEED_OF_LIGHT / (wl * 1e-9)
        s21 = _dc_through_db(p["gap_nm"], p["length_um"], wl)
        phase = (wl % 360) - 180
        # S11 S21 S12 S22  (Touchstone 2-port ordering)
        lines.append(
            f"{freq:.6e}  -28.0 0.0  {s21:.4f} {phase:.2f}  {s21:.4f} {phase:.2f}  -28.0 0.0"
        )
    path.write_text("\n".join(lines) + "\n")


def _gen_ysplitters(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for w in _YS_WIDTHS:
        for a in _YS_ANGLES:
            for t in _YS_TAPERS:
                if w == 550 and a == 15:      # leave a coverage gap
                    continue
                p = {"width_nm": w, "angle_deg": a, "taper_um": t}
                base = out / f"ys_w{w}_a{a}_t{t}"
                _write_lsf(base.with_suffix(".lsf"), "y_splitter", p)
                _write_ys_results(base, p)
                _write_ys_gds(base.with_suffix(".gds"), p)
                n += 1
    return n


def _gen_couplers(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for g in _DC_GAPS:
        for L in _DC_LENGTHS:
            if g == 350 and L >= 30:          # leave a coverage gap
                continue
            p = {"width_nm": 500, "gap_nm": g, "length_um": L}
            base = out / f"dc_gap{g}_L{L}"
            _write_lsf(base.with_suffix(".lsf"), "directional_coupler", p)
            _write_dc_s2p(base.with_suffix(".s2p"), p)
            n += 1
    return n


def _gen_meep(out: Path, rng: random.Random) -> int:
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for w, a, t in ((500, 10, 15), (500, 12, 20), (450, 8, 10)):
        loss = _ys_loss_db(w, a, t, 1550)
        meta = {
            "solver": "meep",
            "parameters": {
                "wg_width": w * 1e-9,
                "branch_angle": a,
                "taper_length": t * 1e-6,
                "resolution": 30,
                "wavelength": 1.55e-6,
                "runtime": round(rng.uniform(1.5, 3.5), 2) * 3600,
            },
            "results": {"insertion_loss_db": round(-loss, 4)},
        }
        base = out / f"meep_ys_w{w}_a{a}_t{t}"
        base.with_suffix(".json").write_text(json.dumps(meta, indent=2))
        flux = ["wavelength_nm,flux"]
        for i in range(31):
            wl = 1500 + i * 3
            flux.append(f"{wl},{10 ** (_ys_loss_db(w, a, t, wl) / 10):.6f}")
        base.with_name(base.name + "_flux").with_suffix(".csv").write_text("\n".join(flux) + "\n")
        n += 1
    return n


def _gen_noise(root: Path) -> None:
    exports = root / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    (exports / "notes.txt").write_text("Lab notebook: rerun ysplitter at 1310nm next week.\n")
    (root / "README.md").write_text("# Photonics project archive\nMixed simulation outputs.\n")


def generate(root: str | Path, *, seed: int = 7, clean: bool = False) -> dict[str, int]:
    """Create the synthetic repository under ``root``. Returns per-family counts."""
    root = Path(root)
    if clean and root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    counts = {
        "y_splitter": _gen_ysplitters(root / "ysplitter_v1"),
        "directional_coupler": _gen_couplers(root / "directional_coupler"),
        "meep_y_splitter": _gen_meep(root / "sweeps" / "meep", rng),
    }
    _gen_noise(root)

    # create a byte-identical duplicate to exercise duplicate detection
    src = next((root / "directional_coupler").glob("*.s2p"))
    shutil.copyfile(src, root / "exports" / f"DUP_{src.name}")
    return counts
