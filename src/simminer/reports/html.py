"""Render analysis + readiness results as a standalone HTML report or text."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .readiness import ReadinessReport

if TYPE_CHECKING:
    from ..pipeline import AnalysisResult

_LABEL_COLOR = {"High": "#1a9850", "Medium": "#e6a000", "Low": "#d73027"}

_STYLE = """
  :root { font-family: -apple-system, Segoe UI, Roboto, sans-serif; }
  body { margin:0; background:#f5f6f8; color:#1d2330; }
  header.top { background:#10233f; color:#fff; padding:24px 32px; }
  header.top h1 { margin:0; font-size:20px; }
  header.top p { margin:4px 0 0; color:#9fb3d1; font-size:13px; }
  main { max-width:980px; margin:24px auto; padding:0 16px; }
  .summary { display:flex; gap:16px; flex-wrap:wrap; margin-bottom:24px; }
  .summary table { background:#fff; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,.08);
                    border-collapse:collapse; overflow:hidden; min-width:240px; }
  .summary caption { text-align:left; font-weight:600; padding:10px 14px; background:#eef1f6; }
  td, th { padding:7px 14px; border-top:1px solid #eef1f6; font-size:14px; }
  .card { background:#fff; border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,.08);
           padding:18px 20px; margin-bottom:18px; }
  .card header { display:flex; align-items:center; justify-content:space-between; }
  .card h3 { margin:0; text-transform:capitalize; }
  .badge { color:#fff; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:600; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; margin:14px 0; }
  .grid .k { display:block; color:#6b7686; font-size:12px; }
  .grid .v { display:block; font-size:15px; font-weight:600; }
  table.metrics { width:100%; border-collapse:collapse; }
  table.metrics td:first-child { width:160px; color:#42506a; font-size:13px; }
  .bar { position:relative; background:#eef1f6; border-radius:4px; height:18px; }
  .bar .fill { height:100%; border-radius:4px; }
  .bar span { position:absolute; right:8px; top:0; font-size:12px; line-height:18px; color:#1d2330; }
  h4 { margin:16px 0 6px; font-size:13px; color:#42506a; text-transform:uppercase; letter-spacing:.04em; }
  ul.notes { margin:6px 0; color:#8a4b00; font-size:13px; }
"""


def _bar(value: float, color: str = "#3a6ea5") -> str:
    pct = max(0.0, min(1.0, value)) * 100
    return (
        f'<div class="bar"><div class="fill" style="width:{pct:.0f}%;'
        f'background:{color}"></div><span>{value:.2f}</span></div>'
    )


def render_text(analysis: "AnalysisResult", reports: list[ReadinessReport]) -> str:
    d = analysis.discovery
    lines: list[str] = []
    lines.append("Simulation Data Miner - Analysis Report")
    lines.append("=" * 44)
    lines.append(f"Root            : {d.root}")
    lines.append(f"Files discovered: {d.total_files}")
    lines.append(f"Logical runs    : {len(d.run_keys)}")
    lines.append(f"Duplicate groups: {len(d.duplicate_groups)}")
    lines.append("")
    lines.append("Component breakdown:")
    for comp, n in analysis.component_counts().items():
        lines.append(f"  - {comp:<22} {n}")
    lines.append("")
    lines.append("Surrogate readiness:")
    for r in reports:
        lines.append(f"  [{r.component_type}]")
        lines.append(f"     runs={r.n_runs} usable={r.n_usable}  features={', '.join(r.features) or '-'}")
        lines.append(
            f"     coverage={r.coverage}  density={r.density}  "
            f"diversity={r.diversity}  output_stability={r.output_stability}"
        )
        lines.append(
            f"     readiness={r.readiness_score} ({r.readiness_label})  "
            f"model={r.suggested_model}"
        )
        lines.append(f"     est. compute savings: {r.estimated_compute_savings_hours} hrs")
        for note in r.notes:
            lines.append(f"       ! {note}")
    if not reports:
        lines.append("  (no recognized component clusters)")
    return "\n".join(lines)


def _report_card(r: ReadinessReport) -> str:
    color = _LABEL_COLOR.get(r.readiness_label, "#888")
    feat_rows = "".join(
        f"<tr><td>{html.escape(f)}</td><td>{_bar(c)}</td></tr>"
        for f, c in r.per_feature_coverage.items()
    ) or "<tr><td colspan=2>no numeric features</td></tr>"
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in r.notes)
    return f"""
    <section class="card">
      <header>
        <h3>{html.escape(r.component_type)}</h3>
        <span class="badge" style="background:{color}">{r.readiness_label} &middot; {r.readiness_score:.2f}</span>
      </header>
      <div class="grid">
        <div><span class="k">Runs</span><span class="v">{r.n_runs}</span></div>
        <div><span class="k">Usable</span><span class="v">{r.n_usable}</span></div>
        <div><span class="k">Suggested model</span><span class="v">{html.escape(r.suggested_model)}</span></div>
        <div><span class="k">Est. compute savings</span><span class="v">{r.estimated_compute_savings_hours:.0f} hrs</span></div>
      </div>
      <table class="metrics">
        <tr><td>Coverage</td><td>{_bar(r.coverage)}</td></tr>
        <tr><td>Density</td><td>{_bar(r.density)}</td></tr>
        <tr><td>Diversity</td><td>{_bar(r.diversity)}</td></tr>
        <tr><td>Output stability</td><td>{_bar(r.output_stability)}</td></tr>
      </table>
      <h4>Per-parameter coverage</h4>
      <table class="metrics">{feat_rows}</table>
      {f'<h4>Notes</h4><ul class="notes">{notes}</ul>' if notes else ''}
    </section>"""


def render_html(analysis: "AnalysisResult", reports: list[ReadinessReport]) -> str:
    d = analysis.discovery
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    comp_rows = "".join(
        f"<tr><td>{html.escape(c)}</td><td>{n}</td></tr>"
        for c, n in analysis.component_counts().items()
    )
    kind_rows = "".join(
        f"<tr><td>{html.escape(k)}</td><td>{n}</td></tr>"
        for k, n in sorted(d.counts_by_kind().items())
    )
    cards = "".join(_report_card(r) for r in reports) or "<p>No recognized component clusters.</p>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>simminer report</title>
<style>{_STYLE}</style></head>
<body>
<header class="top">
  <h1>Simulation Data Miner &mdash; Readiness Report</h1>
  <p>{html.escape(d.root)} &middot; generated {ts}</p>
</header>
<main>
  <div class="summary">
    <table><caption>Inventory</caption>
      <tr><td>Files discovered</td><td>{d.total_files}</td></tr>
      <tr><td>Logical runs</td><td>{len(d.run_keys)}</td></tr>
      <tr><td>Duplicate groups</td><td>{len(d.duplicate_groups)}</td></tr>
    </table>
    <table><caption>Artifacts by kind</caption>{kind_rows}</table>
    <table><caption>Components</caption>{comp_rows or '<tr><td>none</td><td>0</td></tr>'}</table>
  </div>
  <h2>Surrogate readiness</h2>
  {cards}
</main>
</body></html>"""


def _rate_badge(rate: float) -> str:
    color = "#1a9850" if rate >= 0.95 else "#e6a000" if rate >= 0.8 else "#d73027"
    return f'<span class="badge" style="background:{color}">{rate:.1%}</span>'


def render_external_html(report: dict) -> str:
    """Render a ``run_external`` Tier-2 validation report as standalone HTML."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    disc = report["discovery"]
    cls = report["classification"]
    fid = report["parser_fidelity"]

    filetype_rows = "".join(
        f"<tr><td>.{html.escape(str(k))}</td><td>{n}</td></tr>"
        for k, n in sorted(disc.get("counts_by_filetype", {}).items())
    ) or "<tr><td>none</td><td>0</td></tr>"
    comp_rows = "".join(
        f"<tr><td>{html.escape(c)}</td><td>{n}</td></tr>"
        for c, n in cls.get("component_counts", {}).items()
    ) or "<tr><td>none</td><td>0</td></tr>"

    # confusion matrix: expected (rows) x predicted (cols)
    confusion = cls.get("confusion", {})
    predicted = sorted({g for row in confusion.values() for g in row})
    if confusion:
        head = "".join(f"<th>{html.escape(p)}</th>" for p in predicted)
        conf_body = "".join(
            "<tr><td>" + html.escape(exp) + "</td>"
            + "".join(
                f"<td>{confusion[exp].get(p, 0)}</td>" for p in predicted
            )
            + "</tr>"
            for exp in sorted(confusion)
        )
        confusion_html = (
            f'<table class="metrics"><tr><th>expected \\ predicted</th>{head}</tr>'
            f"{conf_body}</table>"
        )
    else:
        confusion_html = "<p>No labeled runs to score.</p>"

    yb_mean = fid["ybranch_insertion_loss_mean_db"]
    yb_block = (
        f"""
        <div><span class="k">Y-branch loss (mean)</span>
          <span class="v">{yb_mean} dB</span></div>
        <div><span class="k">Within 2.5-5 dB</span>
          <span class="v">{fid['ybranch_within_3db_rate']:.1%} (n={fid['ybranch_n']})</span></div>"""
        if fid["ybranch_n"]
        else ""
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>simminer external validation</title>
<style>{_STYLE}</style></head>
<body>
<header class="top">
  <h1>Simulation Data Miner &mdash; External Validation (Tier 2)</h1>
  <p>{html.escape(report['root'])} &middot; generated {ts}</p>
</header>
<main>
  <div class="summary">
    <table><caption>Discovery</caption>
      <tr><td>Files discovered</td><td>{disc['files_discovered']}</td></tr>
      <tr><td>Logical runs</td><td>{disc['logical_runs']}</td></tr>
      <tr><td>Duplicate groups</td><td>{disc['duplicate_groups']}</td></tr>
    </table>
    <table><caption>Files by type</caption>{filetype_rows}</table>
    <table><caption>Components</caption>{comp_rows}</table>
  </div>

  <section class="card">
    <header>
      <h3>Classification</h3>
      {_rate_badge(cls['accuracy'])}
    </header>
    <div class="grid">
      <div><span class="k">Labeled runs scored</span><span class="v">{cls['n_scored']}</span></div>
      <div><span class="k">Accuracy</span><span class="v">{cls['accuracy']:.1%}</span></div>
    </div>
    <h4>Confusion matrix</h4>
    {confusion_html}
  </section>

  <section class="card">
    <header>
      <h3>Parser fidelity (physics checks)</h3>
      {_rate_badge(fid['passivity_ok_rate'])}
    </header>
    <div class="grid">
      <div><span class="k">S-param traces</span><span class="v">{fid['n_sparam_records']}</span></div>
      <div><span class="k">Passivity OK</span><span class="v">{fid['passivity_ok_rate']:.1%}</span></div>{yb_block}
      <div><span class="k">GDS layouts</span><span class="v">{fid['gds_records']}</span></div>
      <div><span class="k">GDS with polygons</span><span class="v">{fid['gds_with_polygons_rate']:.1%}</span></div>
    </div>
    <table class="metrics">
      <tr><td>Passivity OK rate</td><td>{_bar(fid['passivity_ok_rate'])}</td></tr>
      <tr><td>GDS polygon rate</td><td>{_bar(fid['gds_with_polygons_rate'])}</td></tr>
    </table>
  </section>
</main>
</body></html>"""
