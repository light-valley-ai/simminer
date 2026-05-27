"""Core data structures shared across the simminer pipeline.

Everything here is plain ``dataclass`` / ``Enum`` with ``to_dict`` helpers so the
whole pipeline can be serialized to JSON without any third-party dependency.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class FileKind(str, Enum):
    """Coarse role a file plays in a simulation workflow."""

    SIMULATION = "simulation"  # solver project / setup scripts (.fsp, .lsf, .h5 ...)
    GEOMETRY = "geometry"      # layout / geometry (.gds, .oas, geometry .json)
    RESULT = "result"          # solver outputs (.s2p, monitor .csv, spectra ...)
    UNKNOWN = "unknown"


class ComponentType(str, Enum):
    """Photonic component families simminer can recognize.

    MVP classification targets Y-splitters and directional couplers; the other
    members are recognized opportunistically but not deeply analyzed yet.
    """

    Y_SPLITTER = "y_splitter"
    DIRECTIONAL_COUPLER = "directional_coupler"
    RING_RESONATOR = "ring_resonator"
    GRATING_COUPLER = "grating_coupler"
    UNKNOWN = "unknown"


# File extension -> kind. Used by the discovery engine for fast classification.
EXTENSION_KIND: dict[str, FileKind] = {
    "fsp": FileKind.SIMULATION,
    "lsf": FileKind.SIMULATION,
    "lms": FileKind.SIMULATION,
    "h5": FileKind.SIMULATION,
    "hdf5": FileKind.SIMULATION,
    "mat": FileKind.SIMULATION,
    "npz": FileKind.SIMULATION,
    "ctl": FileKind.SIMULATION,  # Meep control scripts
    "gds": FileKind.GEOMETRY,
    "gdsii": FileKind.GEOMETRY,
    "oas": FileKind.GEOMETRY,
    "s2p": FileKind.RESULT,
    "s4p": FileKind.RESULT,
    "sparam": FileKind.RESULT,  # Lumerical INTERCONNECT S-parameter export
    "csv": FileKind.RESULT,
    "dat": FileKind.RESULT,
    "txt": FileKind.RESULT,
    # ``json`` is ambiguous (geometry export vs. result dump); resolved by content.
    "json": FileKind.UNKNOWN,
}


@dataclass
class Artifact:
    """A single discovered file on disk."""

    path: str
    relpath: str
    kind: FileKind
    filetype: str
    size_bytes: int
    sha256: str
    mtime: float
    run_key: Optional[str] = None  # groups files belonging to one simulation run

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kind"] = self.kind.value
        return d


@dataclass
class SimulationRecord:
    """One logical simulation run, merged from its constituent artifacts.

    A run typically bundles a solver script (geometry + sim setup) with one or
    more result files (S-parameters, spectra). Metadata dictionaries hold the
    normalized engineering values extracted by the parsers.
    """

    run_key: str
    component_type: ComponentType = ComponentType.UNKNOWN
    classification_confidence: float = 0.0
    classification_reason: str = ""
    geometry: dict[str, Any] = field(default_factory=dict)
    simulation: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    source_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["component_type"] = self.component_type.value
        return d


@dataclass
class DiscoveryResult:
    """Output of the discovery engine."""

    root: str
    artifacts: list[Artifact] = field(default_factory=list)
    duplicate_groups: list[list[str]] = field(default_factory=list)
    run_keys: list[str] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.artifacts)

    def counts_by_kind(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for a in self.artifacts:
            out[a.kind.value] = out.get(a.kind.value, 0) + 1
        return out

    def counts_by_type(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for a in self.artifacts:
            out[a.filetype] = out.get(a.filetype, 0) + 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "total_files": self.total_files,
            "total_runs": len(self.run_keys),
            "counts_by_kind": self.counts_by_kind(),
            "counts_by_filetype": self.counts_by_type(),
            "duplicate_groups": self.duplicate_groups,
            "artifacts": [a.to_dict() for a in self.artifacts],
        }
