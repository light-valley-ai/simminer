from simminer.datasets import build_datasets
from simminer.models import ComponentType
from simminer.pipeline import analyze
from simminer.reports import render_html, render_text, score_all
from simminer.validation import validate_analysis


def test_analyze_classifies_components(example_repo):
    result = analyze(example_repo)
    counts = result.component_counts()
    assert counts.get(ComponentType.Y_SPLITTER.value, 0) > 0
    assert counts.get(ComponentType.DIRECTIONAL_COUPLER.value, 0) > 0


def test_records_have_geometry_and_results(example_repo):
    result = analyze(example_repo)
    dcs = [r for r in result.records if r.component_type is ComponentType.DIRECTIONAL_COUPLER]
    assert dcs
    sample = dcs[0]
    assert "gap_nm" in sample.geometry
    assert "coupling_length_um" in sample.geometry
    assert "insertion_loss_db" in sample.results


def test_meep_records_classified(example_repo):
    result = analyze(example_repo)
    meep = [r for r in result.records if "meep" in r.run_key]
    assert meep
    assert all(r.simulation.get("solver") == "Meep" for r in meep)


def test_build_datasets(example_repo, tmp_path):
    result = analyze(example_repo)
    manifest = build_datasets(result.clusters(), tmp_path / "ds")
    assert "directional_coupler" in manifest["datasets"]
    dc = manifest["datasets"]["directional_coupler"]
    assert dc["n_rows"] > 0
    assert "gap_nm" in dc["feature_columns"]
    assert "insertion_loss_db" in dc["target_columns"]
    assert (tmp_path / "ds" / dc["file"]).exists()
    assert (tmp_path / "ds" / "manifest.json").exists()


def test_readiness_scoring(example_repo):
    result = analyze(example_repo)
    reports = score_all(result.clusters())
    assert reports
    dc = next(r for r in reports if r.component_type == "directional_coupler")
    assert 0.0 <= dc.readiness_score <= 1.0
    assert dc.readiness_label in ("Low", "Medium", "High")
    assert dc.n_usable > 0
    assert "gap_nm" in dc.per_feature_coverage


def test_render_outputs(example_repo):
    result = analyze(example_repo)
    reports = score_all(result.clusters())
    text = render_text(result, reports)
    assert "Surrogate readiness" in text
    html = render_html(result, reports)
    assert "<!doctype html>" in html
    assert "directional_coupler" in html


def test_validation(example_repo):
    result = analyze(example_repo)
    report = validate_analysis(result)
    assert report["parse_rate"] >= 0.8
    assert report["geometry_rate"] > 0.5
    assert report["duplicate_groups"] >= 1
