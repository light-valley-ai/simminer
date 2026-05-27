from pathlib import Path

from simminer.discovery import run_key_for, scan
from simminer.models import FileKind


def test_scan_finds_artifacts(example_repo):
    result = scan(example_repo)
    assert result.total_files > 50
    kinds = result.counts_by_kind()
    assert kinds.get(FileKind.SIMULATION.value, 0) > 0
    assert kinds.get(FileKind.RESULT.value, 0) > 0
    assert kinds.get(FileKind.GEOMETRY.value, 0) > 0  # .gds files


def test_duplicate_detection(example_repo):
    result = scan(example_repo)
    # generator copies one .s2p verbatim into exports/
    assert any(
        any(p.endswith(".s2p") for p in group)
        for group in result.duplicate_groups
    )


def test_run_key_groups_outputs(tmp_path):
    root = tmp_path
    (root / "d").mkdir()
    base = root / "d" / "ys_w500_a10_t15"
    a = run_key_for(Path(str(base) + ".lsf"), root)
    b = run_key_for(Path(str(base) + "_sparams.csv"), root)
    c = run_key_for(Path(str(base) + "_spectrum.csv"), root)
    assert a == b == c == "d/ys_w500_a10_t15"


def test_noise_files_ignored(example_repo):
    result = scan(example_repo)
    rels = {a.relpath for a in result.artifacts}
    assert "README.md" not in rels  # unrecognized extension
