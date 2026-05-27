"""Build per-component, surrogate-ready datasets (geometry -> outputs).

Each row pairs the normalized geometry feature vector (model inputs) with the
extracted scalar result metrics (model targets). Output is one table per
component type, written as Parquet when pandas/pyarrow are available, otherwise
CSV. A ``manifest.json`` records schema and provenance.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from ..geometry.normalize import GEOMETRY_FIELDS, feature_vector
from ..models import SimulationRecord

# Scalar result metrics promoted to dataset target columns when present.
_TARGET_FIELDS = (
    "insertion_loss_db",
    "s21_at_center_db",
    "s21_peak_db",
    "s21_peak_wavelength_nm",
    "resonance_wavelength_nm",
    "peak_wavelength_nm",
    "extinction_db",
    "bandwidth_3db_nm",
)


def records_to_rows(records: list[SimulationRecord]) -> tuple[list[str], list[dict[str, Any]]]:
    """Flatten records into (column_order, rows) for one component cluster."""
    feat_present: set[str] = set()
    targ_present: set[str] = set()
    rows: list[dict[str, Any]] = []

    for r in records:
        fv = feature_vector(r.geometry)
        if not fv:
            continue
        row: dict[str, Any] = {"run_key": r.run_key, "component_type": r.component_type.value}
        for f in GEOMETRY_FIELDS:
            if f in fv:
                row[f] = fv[f]
                feat_present.add(f)
        has_target = False
        for t in _TARGET_FIELDS:
            v = r.results.get(t)
            if isinstance(v, (int, float)) and math.isfinite(v):
                row[t] = round(float(v), 6)
                targ_present.add(t)
                has_target = True
        row["source_files"] = ";".join(r.source_files)
        if fv and has_target:
            rows.append(row)

    columns = (
        ["run_key", "component_type"]
        + [f for f in GEOMETRY_FIELDS if f in feat_present]
        + [t for t in _TARGET_FIELDS if t in targ_present]
        + ["source_files"]
    )
    return columns, rows


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_parquet(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> bool:
    try:
        import pandas as pd
    except ImportError:
        return False
    df = pd.DataFrame(rows, columns=columns)
    try:
        df.to_parquet(path, index=False)
        return True
    except (ImportError, ValueError):
        return False


def build_datasets(
    clusters: dict[str, list[SimulationRecord]],
    out_dir: str | Path,
    *,
    fmt: str = "auto",
) -> dict[str, Any]:
    """Write one dataset file per component cluster into ``out_dir``.

    ``fmt`` is ``"parquet"``, ``"csv"``, or ``"auto"`` (parquet if available).
    Returns a manifest dict (also written to ``manifest.json``).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {"format": fmt, "datasets": {}}

    for comp, records in sorted(clusters.items()):
        if comp == "unknown":
            continue
        columns, rows = records_to_rows(records)
        if not rows:
            continue

        stem = comp + "s" if not comp.endswith("s") else comp
        wrote_parquet = False
        if fmt in ("auto", "parquet"):
            wrote_parquet = _write_parquet(out_dir / f"{stem}.parquet", columns, rows)
        if not wrote_parquet:
            _write_csv(out_dir / f"{stem}.csv", columns, rows)
        path = f"{stem}.parquet" if wrote_parquet else f"{stem}.csv"

        feature_cols = [c for c in columns if c in GEOMETRY_FIELDS]
        target_cols = [c for c in columns if c in _TARGET_FIELDS]
        manifest["datasets"][comp] = {
            "file": path,
            "n_rows": len(rows),
            "feature_columns": feature_cols,
            "target_columns": target_cols,
        }

    manifest["format"] = "parquet" if any(
        d["file"].endswith(".parquet") for d in manifest["datasets"].values()
    ) else ("csv" if manifest["datasets"] else fmt)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
