"""Simulation Data Miner (simminer).

Infrastructure for AI-native photonics workflows: discover, structure, validate,
and operationalize historical photonics simulation data.

The package is organized as a pipeline:

    discovery  ->  parsers  ->  geometry  ->  clustering  ->  datasets  ->  reports

Each stage is importable on its own; see ``simminer.pipeline`` for the glue that
runs them end to end, and ``simminer.cli`` for the command line entry point.
"""

from .models import (
    Artifact,
    ComponentType,
    DiscoveryResult,
    FileKind,
    SimulationRecord,
)

__version__ = "0.1.0"

__all__ = [
    "Artifact",
    "ComponentType",
    "DiscoveryResult",
    "FileKind",
    "SimulationRecord",
    "__version__",
]
