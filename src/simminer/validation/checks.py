"""Lightweight validation checks over an analysis result.

These are trust signals, not solver-grade verification:

* **parse rate**      -- fraction of runs that yielded any metadata.
* **geometry rate**   -- fraction with at least one numeric geometry parameter.
* **output rate**     -- fraction with at least one parseable result metric.
* **duplicate ratio** -- byte-identical files / total files.
* **sparse params**   -- geometry params seen in only a single run (likely typos
  or one-off explorations rather than swept dimensions).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..geometry.normalize import feature_vector

if TYPE_CHECKING:
    from ..pipeline import AnalysisResult


def validate_analysis(analysis: "AnalysisResult") -> dict[str, Any]:
    records = analysis.records
    n = len(records) or 1

    with_geo = sum(1 for r in records if feature_vector(r.geometry))
    with_out = sum(1 for r in records if r.results)
    with_any = sum(1 for r in records if r.geometry or r.simulation or r.results)
    warned = sum(1 for r in records if r.warnings)

    dup_files = sum(len(g) for g in analysis.discovery.duplicate_groups)
    total_files = analysis.discovery.total_files or 1

    # parameters appearing in only one run across the whole repo
    param_runs: dict[str, int] = {}
    for r in records:
        for k in feature_vector(r.geometry):
            param_runs[k] = param_runs.get(k, 0) + 1
    sparse = sorted(k for k, c in param_runs.items() if c == 1)

    return {
        "n_runs": len(records),
        "parse_rate": round(with_any / n, 3),
        "geometry_rate": round(with_geo / n, 3),
        "output_rate": round(with_out / n, 3),
        "runs_with_warnings": warned,
        "duplicate_ratio": round(dup_files / total_files, 3),
        "duplicate_groups": len(analysis.discovery.duplicate_groups),
        "sparse_parameters": sparse,
        "passed": with_any / n >= 0.8 and dup_files / total_files <= 0.5,
    }
