"""Recursive simulation-artifact discovery."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path

from ..models import EXTENSION_KIND, Artifact, DiscoveryResult, FileKind

DEFAULT_IGNORE_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", ".venv", "venv",
    "node_modules", ".idea", ".vscode", ".ipynb_checkpoints",
}

# Suffixes appended to a base run name to denote a derived output file.
# Stripping these lets ``foo.lsf`` and ``foo_sparams.csv`` share one run key.
_OUTPUT_SUFFIXES = (
    "_sparams", "_sparam", "_sparameters", "_spectrum", "_spectra",
    "_flux", "_transmission", "_trans", "_through", "_cross", "_drop",
    "_monitor", "_mon", "_field", "_fields", "_result", "_results",
    "_out", "_output", "_T", "_R",
)

_SUFFIX_RE = re.compile(
    "(" + "|".join(re.escape(s) for s in _OUTPUT_SUFFIXES) + ")$",
    re.IGNORECASE,
)


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _resolve_json_kind(path: Path) -> FileKind:
    """Disambiguate a ``.json`` file as geometry vs. result by peeking inside."""
    try:
        head = path.read_text(errors="ignore")[:4096].lower()
    except OSError:
        return FileKind.UNKNOWN
    geom_hints = ("polygon", "vertices", "coordinates", "layer", "cell", "gds", "width", "radius")
    result_hints = ("s21", "s11", "transmission", "wavelength", "flux", "spectrum")
    geom = sum(h in head for h in geom_hints)
    res = sum(h in head for h in result_hints)
    if geom == 0 and res == 0:
        return FileKind.UNKNOWN
    return FileKind.GEOMETRY if geom >= res else FileKind.RESULT


def classify_kind(path: Path) -> tuple[str, FileKind]:
    ext = path.suffix.lower().lstrip(".")
    kind = EXTENSION_KIND.get(ext, FileKind.UNKNOWN)
    if ext == "json":
        kind = _resolve_json_kind(path)
    return ext, kind


def run_key_for(path: Path, root: Path) -> str:
    """Derive the run grouping key for a file.

    Files in the same directory whose names share a base stem (ignoring known
    output suffixes) belong to the same simulation run.
    """
    rel_parent = path.parent.relative_to(root).as_posix()
    stem = path.stem
    # strip a single trailing output suffix if present
    base = _SUFFIX_RE.sub("", stem)
    base = base or stem
    prefix = rel_parent if rel_parent != "." else ""
    return f"{prefix}/{base}".lstrip("/")


def scan(
    root: str | Path,
    *,
    ignore_dirs: set[str] | None = None,
    follow_symlinks: bool = False,
) -> DiscoveryResult:
    """Walk ``root`` and return a :class:`DiscoveryResult`.

    Only files with a recognized photonics extension (or content-resolved JSON)
    are kept; everything else is ignored as noise.
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")
    ignore = ignore_dirs if ignore_dirs is not None else DEFAULT_IGNORE_DIRS

    artifacts: list[Artifact] = []
    by_hash: dict[str, list[str]] = defaultdict(list)
    run_keys: set[str] = set()

    for path in sorted(root.rglob("*")):
        if any(part in ignore for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.is_symlink() and not follow_symlinks:
            continue

        ext, kind = classify_kind(path)
        if kind is FileKind.UNKNOWN and ext not in EXTENSION_KIND:
            continue  # unrecognized extension -> not a simulation artifact

        try:
            stat = path.stat()
            digest = _sha256(path)
        except OSError:
            continue

        rk = run_key_for(path, root)
        run_keys.add(rk)
        artifact = Artifact(
            path=str(path),
            relpath=path.relative_to(root).as_posix(),
            kind=kind,
            filetype=ext,
            size_bytes=stat.st_size,
            sha256=digest,
            mtime=stat.st_mtime,
            run_key=rk,
        )
        artifacts.append(artifact)
        by_hash[digest].append(artifact.relpath)

    duplicate_groups = sorted(
        (sorted(paths) for paths in by_hash.values() if len(paths) > 1),
        key=lambda g: g[0],
    )

    return DiscoveryResult(
        root=str(root),
        artifacts=artifacts,
        duplicate_groups=duplicate_groups,
        run_keys=sorted(run_keys),
    )
