# Status

_Last updated: 2026-05-26_

## Summary

The **MVP is implemented and working end to end.** The full pipeline runs from a
directory of mixed simulation artifacts to surrogate-ready datasets and a
readiness report, with a synthetic data generator, a test suite, and benchmarks
that prove it against known ground truth.

## What works today

| Stage | Status | Notes |
|-------|--------|-------|
| Discovery | ✅ | Recursive scan, file-type ID, sha256 dedup, run grouping |
| Metadata extraction | ✅ | `.lsf`, `.s2p`, CSV S-params/spectra, Meep JSON/flux, GDSII, geometry JSON |
| Geometry normalization | ✅ | Unit inference (m/µm/nm), canonical fields, feature vectors |
| Classification | ✅ | Heuristic: filename keywords + parameter fingerprints |
| Dataset builder | ✅ | Per-component Parquet (CSV fallback) + `manifest.json` |
| Readiness scoring | ✅ | Coverage / density / diversity / output-stability → label + model + savings |
| Validation | ✅ | Parse/geometry/output rates, duplicate ratio, sparse-param detection |
| Benchmarks | ✅ | Classification & metadata accuracy vs. synthetic ground truth |
| CLI | ✅ | `gen-examples`, `scan`, `analyze`, `build-dataset`, `report`, `validate`, `benchmark` |

## Verified results (synthetic repo, 196 files / 66 runs)

```
$ simminer benchmark ./example_repo
  discovery: 196 files, 66 runs, dup-detection OK
  classification accuracy : 100.0%  (n=65)
  metadata extraction acc : 98.8%  (n=166 fields)
```

- The 2 metadata misses are the intentionally-planted duplicate `.s2p` (a
  results-only file with no geometry script — correctly has no recovered
  geometry).
- Readiness for both component families currently scores **Medium**: parameter
  sweeps are one-sim-per-grid-point (low density) and several dimensions are
  coarsely sampled (low coverage) — an honest reflection of single-pass sweeps.
- `pytest`: **20 passed**.

## Tech stack (as built)

- **Core**: pure Python + Typer (no hard scientific dependency).
- **Optional extras**: `data` (numpy/pandas/pyarrow → Parquet), `viz` (plotly).
- GDSII is read/written by a built-in module — no `gdstk`/`gdspy` needed, which
  matters on Python 3.14 where those wheels may be unavailable.

## Known limitations / MVP boundaries

- Binary containers (`.fsp`, `.h5`, `.mat`, `.npz`, `.oas`) are discovered and
  inventoried but **not parsed** (no metadata extracted).
- Classification is heuristic; rings and grating couplers are recognized by
  keyword/params but not deeply validated.
- The HTML report uses static inline bars (no plotly charts yet).
- Constant parameters (e.g. fixed waveguide thickness) are still listed as
  features and depress coverage/diversity slightly.

## Next steps (post-MVP)

1. Parse binary containers (`h5py` for `.h5`/Lumerical exports) behind the
   optional `data` extra.
2. Drop zero-variance columns from feature sets in datasets/readiness.
3. Plotly charts (parameter heatmaps, spectrum clustering, missing-region maps)
   in the HTML report under the `viz` extra.
4. Phase 2: a reference `geometry → S21` surrogate trainer consuming the built
   datasets (see [GOALS.md](GOALS.md) roadmap).
5. Geometry-embedding similarity to replace heuristic classification.
