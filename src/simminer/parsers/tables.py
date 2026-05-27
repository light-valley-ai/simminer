"""Small stdlib CSV helpers shared by the result parsers."""

from __future__ import annotations

import csv
import math
from pathlib import Path


def read_numeric_csv(path: str | Path) -> tuple[list[str], dict[str, list[float]]]:
    """Read a CSV with a header row into ``(header, columns)``.

    Non-numeric cells become ``nan``. Comment lines starting with ``#`` or ``!``
    and blank lines are skipped. Header names are lowercased and stripped.
    """
    rows: list[list[str]] = []
    with Path(path).open(newline="", errors="ignore") as fh:
        for raw in csv.reader(fh):
            if not raw:
                continue
            first = raw[0].strip()
            if first.startswith(("#", "!", "%")):
                continue
            rows.append(raw)
    if not rows:
        return [], {}

    header = [h.strip().lower() for h in rows[0]]
    columns: dict[str, list[float]] = {h: [] for h in header}
    for row in rows[1:]:
        for i, h in enumerate(header):
            cell = row[i].strip() if i < len(row) else ""
            try:
                columns[h].append(float(cell))
            except ValueError:
                columns[h].append(math.nan)
    return header, columns


def find_column(header: list[str], *needles: str) -> str | None:
    """Return the first header containing any of ``needles`` (substring match)."""
    for h in header:
        for n in needles:
            if n in h:
                return h
    return None
