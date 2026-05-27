"""Surrogate-readiness scoring for a classified component cluster.

The scores answer: *does enough structured data exist to train a surrogate?*

* **coverage**  -- how much of each parameter's range is sampled (occupied bins).
* **density**   -- how many examples per occupied region of the joint space.
* **diversity** -- normalized entropy of the parameter distributions.
* **output stability** -- fraction of runs with a usable, finite output target.

These combine into a 0-1 readiness score with a qualitative label, a suggested
surrogate model class, and an estimated reuse compute saving.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any

from ..geometry.normalize import feature_vector
from ..models import SimulationRecord

# Output fields that can serve as a surrogate training target, best first.
_TARGET_FIELDS = (
    "insertion_loss_db",
    "s21_at_center_db",
    "resonance_wavelength_nm",
    "extinction_db",
    "bandwidth_3db_nm",
)
# Assumed wall-clock hours per FDTD run when scripts don't record a runtime.
_DEFAULT_RUNTIME_HOURS = 2.0


@dataclass
class ReadinessReport:
    component_type: str
    n_runs: int
    n_usable: int
    features: list[str]
    coverage: float
    density: float
    diversity: float
    output_stability: float
    readiness_score: float
    readiness_label: str
    suggested_model: str
    estimated_compute_savings_hours: float
    per_feature_coverage: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _n_bins(n: int) -> int:
    return max(3, min(10, n // 2 or 1))


def _bin_index(value: float, lo: float, hi: float, nbins: int) -> int:
    if hi <= lo:
        return 0
    frac = (value - lo) / (hi - lo)
    return min(nbins - 1, max(0, int(frac * nbins)))


def _primary_target(record: SimulationRecord) -> float | None:
    for f in _TARGET_FIELDS:
        v = record.results.get(f)
        if isinstance(v, (int, float)) and math.isfinite(v):
            return float(v)
    return None


def score_cluster(component_type: str, records: list[SimulationRecord]) -> ReadinessReport:
    n_runs = len(records)
    feats = [feature_vector(r.geometry) for r in records]
    # features present in at least one record
    feature_names = sorted({k for fv in feats for k in fv})

    usable = [r for r in records if _primary_target(r) is not None and feature_vector(r.geometry)]
    n_usable = len(usable)
    output_stability = round(n_usable / n_runs, 3) if n_runs else 0.0

    nbins = _n_bins(n_runs)
    per_feature_cov: dict[str, float] = {}
    diversities: list[float] = []
    binned_rows: list[tuple[int, ...]] = []

    for name in feature_names:
        vals = [fv[name] for fv in feats if name in fv]
        lo, hi = min(vals), max(vals)
        occupied = {_bin_index(v, lo, hi, nbins) for v in vals}
        per_feature_cov[name] = round(len(occupied) / nbins, 3)
        # entropy over occupied bins
        counts: dict[int, int] = {}
        for v in vals:
            b = _bin_index(v, lo, hi, nbins)
            counts[b] = counts.get(b, 0) + 1
        total = sum(counts.values())
        ent = -sum((c / total) * math.log(c / total) for c in counts.values())
        diversities.append(ent / math.log(nbins) if nbins > 1 else 0.0)

    # joint occupancy for density
    for fv in feats:
        if not fv:
            continue
        row = []
        for name in feature_names:
            if name in fv:
                vals = [g[name] for g in feats if name in g]
                row.append(_bin_index(fv[name], min(vals), max(vals), nbins))
        binned_rows.append(tuple(row))
    occupied_cells = len(set(binned_rows)) or 1
    mean_per_cell = len(binned_rows) / occupied_cells
    density = round(min(1.0, mean_per_cell / 3.0), 3)  # ~3 samples/cell = saturated

    coverage = round(mean(per_feature_cov.values()), 3) if per_feature_cov else 0.0
    diversity = round(mean(diversities), 3) if diversities else 0.0

    # weighted overall readiness
    score = round(
        0.35 * coverage + 0.25 * density + 0.20 * diversity + 0.20 * output_stability, 3
    )
    if score >= 0.7 and n_usable >= 50:
        label = "High"
    elif score >= 0.45 and n_usable >= 20:
        label = "Medium"
    else:
        label = "Low"

    suggested = _suggest_model(len(feature_names), n_usable)

    # compute-savings estimate
    runtimes = [
        r.simulation.get("runtime_s", 0) / 3600.0
        for r in records
        if isinstance(r.simulation.get("runtime_s"), (int, float))
    ]
    avg_hr = mean([h for h in runtimes if h > 0]) if any(h > 0 for h in runtimes) else _DEFAULT_RUNTIME_HOURS
    savings = round(n_usable * avg_hr, 1)

    notes: list[str] = []
    if n_usable < 20:
        notes.append("Too few usable runs for a reliable surrogate; gather more samples.")
    if coverage < 0.5:
        notes.append("Sparse parameter coverage; sweep underexplored ranges.")
    if output_stability < 0.8:
        notes.append("Some runs lack a parseable output target; check result exports.")
    if not feature_names:
        notes.append("No numeric geometry parameters recovered for this cluster.")

    return ReadinessReport(
        component_type=component_type,
        n_runs=n_runs,
        n_usable=n_usable,
        features=feature_names,
        coverage=coverage,
        density=density,
        diversity=diversity,
        output_stability=output_stability,
        readiness_score=score,
        readiness_label=label,
        suggested_model=suggested,
        estimated_compute_savings_hours=savings,
        per_feature_coverage=per_feature_cov,
        notes=notes,
    )


def _suggest_model(n_features: int, n_usable: int) -> str:
    if n_usable < 20:
        return "Insufficient data (collect more runs)"
    if n_usable < 100:
        return "Gaussian Process / Kriging (data-efficient)"
    if n_features <= 6:
        return "MLP (multilayer perceptron)"
    return "Gradient-boosted trees or MLP ensemble"


def score_all(clusters: dict[str, list[SimulationRecord]]) -> list[ReadinessReport]:
    reports = [
        score_cluster(comp, recs)
        for comp, recs in clusters.items()
        if comp != "unknown"
    ]
    reports.sort(key=lambda r: r.n_runs, reverse=True)
    return reports
