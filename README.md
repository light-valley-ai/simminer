# Simulation Data Miner (`simminer`)

**Infrastructure for AI-native photonics workflows.**

Silicon photonics teams accumulate years of FDTD runs, parameter sweeps, GDS
variants, and S-parameter exports — scattered across engineer-local folders with
inconsistent naming and no shared structure. `simminer` discovers those
artifacts, extracts engineering metadata, classifies the components, and turns
them into **searchable, surrogate-ready datasets** with a **readiness report**
that tells you whether you have enough data to train a surrogate model.

> The goal is not to replace physics solvers. The goal is to make existing
> simulation data usable by AI-assisted design, optimization, and verification.

## Pipeline

```
Filesystem ─► Discovery ─► Metadata Extraction ─► Geometry Normalization
           ─► Component Classification ─► Dataset Builder ─► Readiness Report
```

Each stage lives in its own subpackage (`discovery/`, `parsers/`, `geometry/`,
`clustering/`, `datasets/`, `reports/`, `validation/`) and is independently
importable. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"     # core + parquet datasets + viz
```

Core parsing and reporting work with **zero third-party dependencies** beyond
Typer. The `data` extra (numpy/pandas/pyarrow) enables Parquet dataset export;
without it, datasets fall back to CSV.

## Quickstart

```bash
# 1. Generate a synthetic photonics repo (no real data needed to try it)
simminer gen-examples ./example_repo

# 2. Discover and inventory artifacts
simminer scan ./example_repo

# 3. Extract metadata + classify components
simminer analyze ./example_repo

# 4. Build surrogate-ready datasets (geometry -> S-parameters)
simminer build-dataset ./example_repo -o datasets/

# 5. Generate a readiness report (text + standalone HTML)
simminer report ./example_repo -o report.html

# 6. Validate parsing / dataset quality
simminer validate ./example_repo
```

## MVP scope

The first release deliberately targets **Y-splitters** and **directional
couplers** from **Lumerical** (`.lsf`) and **Meep** exports, with **S-parameter**
and **spectrum** outputs. Other components (rings, grating couplers) and binary
container formats (`.fsp`, `.h5`, `.mat`) are recognized during discovery but not
yet deeply parsed. See [`docs/STATUS.md`](docs/STATUS.md) for the live status.

## Supported formats

| Stage     | Parsed today                                  | Recognized (not parsed) |
|-----------|-----------------------------------------------|-------------------------|
| Setup     | `.lsf` (Lumerical script), Meep `.json`       | `.fsp`, `.ctl`          |
| Geometry  | `.gds` (built-in reader), geometry `.json`    | `.oas`                  |
| Results   | `.s2p` (Touchstone), `.csv` S-params/spectra, Meep flux `.csv` | `.h5`, `.mat`, `.npz` |

## Development

```bash
pip install -e ".[dev]"
pytest                      # run the test suite
```

## License

MIT — see [LICENSE](LICENSE).
