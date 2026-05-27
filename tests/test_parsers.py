import math

from simminer.parsers import gds, units
from simminer.parsers.lsf import parse_lsf
from simminer.parsers.sparam import parse_sparam_csv, parse_touchstone
from simminer.parsers.spectra import parse_spectrum_csv


def test_unit_inference():
    assert units.to_nm(0.5e-6) == 500.0   # SI meters
    assert units.to_nm(0.5) == 500.0      # micrometers
    assert units.to_nm(500) == 500.0      # nanometers
    assert units.to_um(20e-6) == 20.0


def test_lsf_geometry_extraction(tmp_path):
    p = tmp_path / "ys.lsf"
    p.write_text(
        "addfdtd;\n"
        "wg_width = 0.5e-6;\n"
        "branch_angle = 12;\n"
        "taper_length = 20e-6;\n"
        'set("mesh accuracy", 3);\n'
        'set("wavelength start", 1.5e-6);\n'
    )
    out = parse_lsf(p)
    assert out["geometry"]["width_nm"] == 500.0
    assert out["geometry"]["branch_angle_deg"] == 12
    assert out["geometry"]["taper_length_um"] == 20.0
    assert out["simulation"]["solver"] == "FDTD"
    assert out["simulation"]["mesh_accuracy"] == 3
    assert out["simulation"]["wavelength_start_nm"] == 1500.0


def test_lsf_safe_eval_handles_expressions(tmp_path):
    p = tmp_path / "x.lsf"
    p.write_text("wg_width = 500 * 1e-9;\n")
    assert parse_lsf(p)["geometry"]["width_nm"] == 500.0


def test_touchstone_roundtrip(tmp_path):
    p = tmp_path / "dc.s2p"
    lines = ["# HZ S DB R 50"]
    c = units.SPEED_OF_LIGHT
    for wl in (1540, 1550, 1560):
        f = c / (wl * 1e-9)
        lines.append(f"{f:.6e} -28 0 -3.0 10 -3.0 10 -28 0")
    p.write_text("\n".join(lines))
    res = parse_touchstone(p)["results"]
    assert res["n_points"] == 3
    assert math.isclose(res["s21_peak_db"], -3.0, abs_tol=1e-6)
    assert math.isclose(res["insertion_loss_db"], 3.0, abs_tol=1e-6)


def test_sparam_csv(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("wavelength_nm,S21_dB,S11_dB\n1540,-3.2,-25\n1550,-3.0,-26\n1560,-3.3,-25\n")
    res = parse_sparam_csv(p)["results"]
    assert math.isclose(res["s21_peak_db"], -3.0, abs_tol=1e-6)


def test_spectrum_csv(tmp_path):
    p = tmp_path / "spec.csv"
    p.write_text("wavelength_nm,transmission_db\n1500,-3.5\n1550,-3.0\n1600,-3.6\n")
    res = parse_spectrum_csv(p)["results"]
    assert res["peak_wavelength_nm"] == 1550.0
    assert res["units"] == "dB"


def test_gds_write_read_roundtrip(tmp_path):
    p = tmp_path / "wg.gds"
    polys = [[(0, 0), (10, 0), (10, 0.5), (0, 0.5)]]
    gds.write_gds(p, polys)
    out = gds.read_gds(p)["geometry"]
    assert out["polygon_count"] == 1
    assert math.isclose(out["bbox_width_um"], 10.0, abs_tol=1e-3)
    assert math.isclose(out["bbox_height_um"], 0.5, abs_tol=1e-3)
    assert "geometry_hash" in out


def test_real8_roundtrip():
    for v in (1e-9, 1e-6, 0.001, 1.0, -42.5, 1550.0):
        enc = gds._encode_real8(v)
        assert math.isclose(gds._decode_real8(enc), v, rel_tol=1e-9)
