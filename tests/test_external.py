"""Tier-2 external validation test.

Skipped unless SIMMINER_PDK points at a real PDK checkout (e.g. the SiEPIC
EBeam PDK), since that data is not vendored into this repo.
"""

import os

import pytest

from simminer.benchmarks import run_external

_PDK = os.environ.get("SIMMINER_PDK")


@pytest.mark.skipif(not _PDK, reason="set SIMMINER_PDK to a real PDK checkout to run")
def test_external_pdk():
    report = run_external(_PDK)
    assert report["discovery"]["files_discovered"] > 0
    # classification should be strong on the unambiguous labeled families
    assert report["classification"]["n_scored"] > 0
    assert report["classification"]["accuracy"] >= 0.9
    # parsed S-parameters must obey passivity (no |S21| > 0 dB)
    fid = report["parser_fidelity"]
    if fid["n_sparam_records"]:
        assert fid["passivity_ok_rate"] >= 0.95
