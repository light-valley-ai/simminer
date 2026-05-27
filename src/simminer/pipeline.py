"""End-to-end pipeline: discovery -> parse -> merge -> classify.

This is the single entry point both the CLI and tests build on. It produces an
:class:`AnalysisResult` holding the raw discovery output plus one merged,
classified :class:`SimulationRecord` per logical run.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .clustering.classify import classify_record, cluster_records
from .discovery import scan
from .geometry.normalize import normalize
from .models import Artifact, DiscoveryResult, FileKind, SimulationRecord
from .parsers import parse_file, parse_params_from_name

# Files contributing geometry/sim setup are parsed before result files so that
# their metadata wins on key collisions.
_KIND_ORDER = {FileKind.SIMULATION: 0, FileKind.GEOMETRY: 1, FileKind.RESULT: 2, FileKind.UNKNOWN: 3}


@dataclass
class AnalysisResult:
    discovery: DiscoveryResult
    records: list[SimulationRecord] = field(default_factory=list)

    def clusters(self) -> dict[str, list[SimulationRecord]]:
        return cluster_records(self.records)

    def component_counts(self) -> dict[str, int]:
        return {k: len(v) for k, v in sorted(self.clusters().items())}

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery": {
                "root": self.discovery.root,
                "total_files": self.discovery.total_files,
                "total_runs": len(self.discovery.run_keys),
                "counts_by_kind": self.discovery.counts_by_kind(),
                "counts_by_filetype": self.discovery.counts_by_type(),
                "duplicate_groups": self.discovery.duplicate_groups,
            },
            "component_counts": self.component_counts(),
            "records": [r.to_dict() for r in self.records],
        }


def _merge_into(dst: dict[str, Any], src: dict[str, Any]) -> None:
    for k, v in src.items():
        if v is None:
            continue
        dst.setdefault(k, v)


def _build_record(run_key: str, artifacts: list[Artifact]) -> SimulationRecord:
    record = SimulationRecord(run_key=run_key)
    ordered = sorted(artifacts, key=lambda a: (_KIND_ORDER.get(a.kind, 9), a.relpath))
    for art in ordered:
        record.source_files.append(art.relpath)
        parsed = parse_file(art.path)
        _merge_into(record.geometry, parsed.get("geometry", {}))
        _merge_into(record.simulation, parsed.get("simulation", {}))
        _merge_into(record.results, parsed.get("results", {}))
        record.warnings.extend(parsed.get("warnings", []))
    # Fill geometry gaps from names (often the only source for .sparam/.dat files).
    # File-parsed values take precedence, so this only adds missing fields.
    for name in [*record.source_files, run_key]:
        _merge_into(record.geometry, parse_params_from_name(name))
    record.geometry = normalize(record.geometry)
    comp, conf, reason = classify_record(record)
    record.component_type = comp
    record.classification_confidence = conf
    record.classification_reason = reason
    return record


def analyze(root: str | Path, **scan_kwargs: Any) -> AnalysisResult:
    """Run the full pipeline over ``root``."""
    discovery = scan(root, **scan_kwargs)
    by_run: dict[str, list[Artifact]] = defaultdict(list)
    for art in discovery.artifacts:
        by_run[art.run_key or art.relpath].append(art)

    records = [_build_record(rk, arts) for rk, arts in sorted(by_run.items())]
    return AnalysisResult(discovery=discovery, records=records)
