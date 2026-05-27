"""``simminer`` command line interface."""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .benchmarks import run_benchmarks, run_external
from .datasets import build_datasets
from .discovery import scan
from .examples import generate
from .pipeline import analyze
from .reports import render_html, render_text, score_all
from .validation import validate_analysis

app = typer.Typer(
    add_completion=False,
    help="Discover, structure, and validate photonics simulation data for AI workflows.",
)


def _echo_json(obj) -> None:
    typer.echo(_json.dumps(obj, indent=2))


@app.command()
def version() -> None:
    """Print the simminer version."""
    typer.echo(f"simminer {__version__}")


@app.command("gen-examples")
def gen_examples(
    path: Path = typer.Argument(..., help="Directory to populate with synthetic data."),
    clean: bool = typer.Option(False, "--clean", help="Remove existing contents first."),
) -> None:
    """Generate a synthetic photonics simulation repository for demos/tests."""
    counts = generate(path, clean=clean)
    total = sum(counts.values())
    typer.echo(f"Generated {total} synthetic runs under {path}:")
    for fam, n in counts.items():
        typer.echo(f"  {fam:<22} {n}")


def scan_cmd(  # function name avoids shadowing the imported scan
    path: Path = typer.Argument(..., help="Simulation repository root."),
    json_out: bool = typer.Option(False, "--json", help="Emit full JSON."),
) -> None:
    """Phase 1: discover and inventory simulation artifacts."""
    result = scan(path)
    if json_out:
        _echo_json(result.to_dict())
        return
    typer.echo(f"Scanned {result.root}")
    typer.echo(f"  files : {result.total_files}")
    typer.echo(f"  runs  : {len(result.run_keys)}")
    typer.echo(f"  dupes : {len(result.duplicate_groups)} group(s)")
    typer.echo("  by kind:")
    for k, n in sorted(result.counts_by_kind().items()):
        typer.echo(f"    {k:<12} {n}")
    typer.echo("  by filetype:")
    for k, n in sorted(result.counts_by_type().items()):
        typer.echo(f"    .{k:<10} {n}")


# register with the CLI name "scan"
app.command("scan")(scan_cmd)


def analyze_cmd(
    path: Path = typer.Argument(..., help="Simulation repository root."),
    json_out: bool = typer.Option(False, "--json", help="Emit full JSON."),
) -> None:
    """Phases 1-4: discover, extract metadata, normalize, and classify."""
    result = analyze(path)
    if json_out:
        _echo_json(result.to_dict())
        return
    typer.echo(f"Analyzed {result.discovery.root}")
    typer.echo(f"  runs: {len(result.records)}")
    typer.echo("  components:")
    for comp, n in result.component_counts().items():
        typer.echo(f"    {comp:<22} {n}")


app.command("analyze")(analyze_cmd)


@app.command("build-dataset")
def build_dataset(
    path: Path = typer.Argument(..., help="Simulation repository root."),
    out: Path = typer.Option(Path("datasets"), "-o", "--out", help="Output directory."),
    fmt: str = typer.Option("auto", "--format", help="auto | parquet | csv."),
) -> None:
    """Phase 5: build per-component, surrogate-ready datasets."""
    result = analyze(path)
    manifest = build_datasets(result.clusters(), out, fmt=fmt)
    if not manifest["datasets"]:
        typer.echo("No datasets built (no classified runs with geometry + outputs).")
        raise typer.Exit(code=0)
    typer.echo(f"Wrote {manifest['format']} datasets to {out}:")
    for comp, info in manifest["datasets"].items():
        typer.echo(f"  {info['file']:<24} {info['n_rows']} rows  "
                   f"({len(info['feature_columns'])} features, {len(info['target_columns'])} targets)")


@app.command()
def report(
    path: Path = typer.Argument(..., help="Simulation repository root."),
    out: Optional[Path] = typer.Option(None, "-o", "--out", help="HTML output path."),
) -> None:
    """Phase 6: print a readiness summary and optionally write an HTML report."""
    result = analyze(path)
    reports = score_all(result.clusters())
    typer.echo(render_text(result, reports))
    if out is not None:
        out.write_text(render_html(result, reports))
        typer.echo(f"\nHTML report written to {out}")


@app.command("validate")
def validate_cmd(
    path: Path = typer.Argument(..., help="Simulation repository root."),
    json_out: bool = typer.Option(False, "--json", help="Emit full JSON."),
) -> None:
    """Run validation/quality checks over the extracted data."""
    result = analyze(path)
    report_ = validate_analysis(result)
    if json_out:
        _echo_json(report_)
        return
    status = "PASS" if report_["passed"] else "REVIEW"
    typer.echo(f"Validation: {status}")
    for k in ("parse_rate", "geometry_rate", "output_rate", "duplicate_ratio"):
        typer.echo(f"  {k:<16} {report_[k]}")
    if report_["sparse_parameters"]:
        typer.echo(f"  sparse params   {', '.join(report_['sparse_parameters'])}")


@app.command()
def benchmark(
    path: Optional[Path] = typer.Argument(
        None, help="Labeled repo to score. Omit to generate a fresh synthetic one."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit full JSON."),
) -> None:
    """Score the pipeline against synthetic ground truth (proof it works)."""
    report_ = run_benchmarks(path)
    if json_out:
        _echo_json(report_)
        return
    disc = report_["discovery"]
    typer.echo("Benchmark results")
    typer.echo(f"  discovery: {disc['files_discovered']} files, "
               f"{disc['logical_runs']} runs, "
               f"dup-detection {'OK' if disc['duplicate_detection_ok'] else 'FAIL'}")
    cls = report_["classification"]
    typer.echo(f"  classification accuracy : {cls['accuracy']:.1%}  (n={cls['n']})")
    meta = report_["metadata_extraction"]
    typer.echo(f"  metadata extraction acc : {meta['accuracy']:.1%}  (n={meta['n_fields']} fields)")


@app.command("validate-external")
def validate_external(
    path: Path = typer.Argument(..., help="Root of a real PDK (e.g. a SiEPIC EBeam PDK checkout)."),
    json_out: bool = typer.Option(False, "--json", help="Emit full JSON."),
) -> None:
    """Tier-2 validation: run the pipeline over a real external PDK and score it."""
    report_ = run_external(path)
    if json_out:
        _echo_json(report_)
        return
    disc, cls, fid = report_["discovery"], report_["classification"], report_["parser_fidelity"]
    typer.echo(f"External validation: {report_['root']}")
    typer.echo(f"  discovery     : {disc['files_discovered']} files, "
               f"{disc['logical_runs']} runs, {disc['duplicate_groups']} duplicate groups")
    typer.echo(f"  classification: {cls['accuracy']:.1%} accuracy on {cls['n_scored']} labeled runs")
    typer.echo(f"  S-param parser: passivity OK {fid['passivity_ok_rate']:.1%} "
               f"of {fid['n_sparam_records']} traces")
    if fid["ybranch_n"]:
        typer.echo(f"  Y-branch loss : mean {fid['ybranch_insertion_loss_mean_db']} dB "
                   f"(within 2.5-5 dB: {fid['ybranch_within_3db_rate']:.1%}, n={fid['ybranch_n']})")
    typer.echo(f"  GDS reader    : {fid['gds_with_polygons_rate']:.1%} of "
               f"{fid['gds_records']} layouts yielded polygons")


if __name__ == "__main__":
    app()
