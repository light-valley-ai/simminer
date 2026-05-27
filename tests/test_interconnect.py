"""Tests for the Lumerical INTERCONNECT parser and filename param extraction."""

import math

from simminer.parsers.filename import parse_params_from_name
from simminer.parsers.interconnect import parse_interconnect
from simminer.parsers.units import SPEED_OF_LIGHT


def _write_sparam(path, through_amp=0.7071):
    """Write a minimal 2-port INTERCONNECT .sparam fixture.

    Reflection (port1->port1) is small; through (port2->port1) has the given
    linear amplitude (0.7071 -> -3 dB).
    """
    lines = []
    wls = [1540, 1550, 1560]
    for out_p, in_p, amp in (("port 1", "port 1", 0.01), ("port 2", "port 1", through_amp)):
        lines.append(f"('{out_p}','TE',1,'{in_p}',1,'transmission')")
        lines.append(f"({len(wls)},3)")
        for wl in wls:
            f = SPEED_OF_LIGHT / (wl * 1e-9)
            lines.append(f"{f:.6e} {amp:.6f} 0.0")
    path.write_text("\n".join(lines) + "\n")


def test_interconnect_parses_primary_path(tmp_path):
    p = tmp_path / "dev.sparam"
    _write_sparam(p, through_amp=0.7071)  # -3.01 dB
    res = parse_interconnect(p)["results"]
    assert res["source_format"] == "interconnect"
    assert res["n_ports"] == 2
    assert res["primary_path"] == "port 1->port 2"  # off-diagonal, highest amplitude
    assert math.isclose(res["s21_peak_db"], -3.01, abs_tol=0.05)
    assert math.isclose(res["insertion_loss_db"], 3.01, abs_tol=0.05)


def test_interconnect_passivity(tmp_path):
    p = tmp_path / "dev.sparam"
    _write_sparam(p, through_amp=0.99)
    res = parse_interconnect(p)["results"]
    assert res["s21_peak_db"] <= 0.1  # passive: no gain


def test_filename_units_respected():
    # the critical case: 80 would look like micrometers under magnitude inference,
    # but the explicit "nm" unit must win -> 80 nm.
    params = parse_params_from_name("dc_gap=80nm_Lc=10um")
    assert params["gap_nm"] == 80.0
    assert params["coupling_length_um"] == 10.0


def test_filename_halfring_full():
    name = "ebeam_dc_halfring_straight_te1550_gap=80nm_radius=6um_width=520nm_thickness=210nm_CoupleLength=0um"
    p = parse_params_from_name(name)
    assert p["gap_nm"] == 80.0
    assert p["bend_radius_um"] == 6.0
    assert p["width_nm"] == 520.0
    assert p["thickness_nm"] == 210.0
    assert p["coupling_length_um"] == 0.0


def test_filename_ybranch_spacing():
    p = parse_params_from_name("Ybranch_Thickness =210 width=500")
    assert p["thickness_nm"] == 210.0
    assert p["width_nm"] == 500.0
