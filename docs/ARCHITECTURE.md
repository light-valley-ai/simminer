# Architecture

`simminer` is a linear pipeline. Each stage is a subpackage with a narrow,
independently testable interface; `simminer/pipeline.py` wires them together and
`simminer/cli.py` exposes them as commands.

```
Filesystem / simulation repo
        │
        ▼
┌─────────────────┐   discovery/      recursive scan, file-type ID, dedup,
│   Discovery     │                   run grouping  → DiscoveryResult
└─────────────────┘
        │ Artifacts grouped by run_key
        ▼
┌─────────────────┐   parsers/        per-format extraction:
│ Metadata        │                   .lsf, .s2p, CSV S-params/spectra,
│ Extraction      │                   Meep JSON/flux, GDSII, geometry JSON
└─────────────────┘
        │ partial {geometry, simulation, results}
        ▼
┌─────────────────┐   geometry/       unit-normalized canonical fields +
│ Normalization   │                   numeric feature vectors
└─────────────────┘
        │ SimulationRecord (merged per run)
        ▼
┌─────────────────┐   clustering/     heuristic classification by filename
│ Classification  │                   keywords + parameter fingerprints
└─────────────────┘
        │ records tagged with ComponentType
        ├──────────────► datasets/   per-component geometry→outputs tables
        │                            (Parquet, CSV fallback) + manifest
        │
        ├──────────────► reports/    coverage/density/diversity/stability
        │                            → readiness score + HTML/text report
        │
        └──────────────► validation/ parse rate, geometry rate, dup ratio,
                                     sparse-parameter detection
```

## Key data structures (`simminer/models.py`)

- **`Artifact`** — one discovered file: path, `kind` (simulation/geometry/result),
  filetype, size, sha256, mtime, and a `run_key` grouping related files.
- **`SimulationRecord`** — one logical run, merged from its artifacts, with
  `geometry`, `simulation`, `results` metadata dicts plus a `ComponentType`.
- **`DiscoveryResult`** — the discovery-stage output (artifacts, duplicate
  groups, run keys).

## Run grouping

Files in the same directory whose names share a base stem (ignoring output
suffixes like `_sparams`, `_spectrum`, `_flux`) are treated as one run. So
`ys_w500_a10_t15.lsf`, `..._sparams.csv`, and `..._spectrum.csv` merge into a
single `SimulationRecord`. See `discovery/scanner.py:run_key_for`.

## Unit normalization

Photonics tools mix SI meters, micrometers, and nanometers. `parsers/units.py`
infers the source unit from magnitude and normalizes to a fixed convention:
feature sizes → **nm**, device lengths → **µm**, wavelengths → **nm**.

## Design principles

- **Parsers never crash the pipeline** — each returns partial metadata with a
  `warnings` list; the registry catches exceptions per file.
- **Core has no hard scientific dependency** — numpy/pandas/pyarrow/plotly are
  optional extras; Parquet degrades to CSV, charts degrade to static tables.
- **Heuristics behind stable interfaces** — classification and readiness are
  rule-based today and can be swapped for learned models without changing the
  pipeline contract.

## Extending

- **New format** → add a parser returning `{geometry, simulation, results,
  warnings}` and register it in `parsers/registry.py`.
- **New component** → add keyword/parameter signals in
  `clustering/classify.py` and a `ComponentType` member.
- **New target metric** → add it to `_TARGET_FIELDS` in `datasets/builder.py`
  and `reports/readiness.py`.
