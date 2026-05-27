# Status

_Last updated: 2026-05-26_

## Summary

The **MVP is implemented and working end to end**, and now **validated against a
real public PDK (Tier 2)**. The full pipeline runs from a directory of mixed
simulation artifacts to surrogate-ready datasets and a readiness report, with a
synthetic data generator, a test suite, and benchmarks that prove it against both
synthetic ground truth and the open SiEPIC EBeam PDK.

## What works today

| Stage | Status | Notes |
|-------|--------|-------|
| Discovery | ✅ | Recursive scan, file-type ID, sha256 dedup, run grouping |
| Metadata extraction | ✅ | `.lsf`, `.s2p`, **INTERCONNECT `.sparam`/`.dat`**, CSV S-params/spectra, Meep JSON/flux, GDSII, geometry JSON |
| Filename param mining | ✅ | Unit-aware `key=value` extraction (`gap=80nm`, `Lc=10um`) — often the only geometry source for `.sparam` files |
| Geometry normalization | ✅ | Unit inference (m/µm/nm), canonical fields, feature vectors |
| Classification | ✅ | Heuristic: filename keywords + parameter fingerprints (incl. SiEPIC naming) |
| Dataset builder | ✅ | Per-component Parquet (CSV fallback) + `manifest.json` |
| Readiness scoring | ✅ | Coverage / density / diversity / output-stability → label + model + savings |
| Validation | ✅ | Parse/geometry/output rates, duplicate ratio, sparse-param detection |
| Benchmarks | ✅ | Synthetic ground truth **+ real-PDK external validation** |
| CLI | ✅ | `gen-examples`, `scan`, `analyze`, `build-dataset`, `report`, `validate`, `benchmark`, `validate-external` |

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
- `pytest`: **25 passed, 1 skipped** (external test runs only when `SIMMINER_PDK` is set).

## Tier 2 — validated on real data (SiEPIC EBeam PDK)

Run over a clone of the open [SiEPIC EBeam PDK](https://github.com/SiEPIC/SiEPIC_EBeam_PDK):

```
$ simminer validate-external <pdk>
  discovery     : 2055 files, 2044 runs, 482 duplicate groups
  classification: 99.7% accuracy on 323 labeled runs
  S-param parser: passivity OK 98.0% of 200 traces
  Y-branch loss : mean 3.126 dB (within 2.5-5 dB: 100.0%, n=56)
  GDS reader    : 99.4% of 172 layouts yielded polygons
```

Why these numbers are meaningful:

- **Classification (99.7%)** is scored against folder-derived ground truth on the
  unambiguous families we target (Y-branch, directional coupler, grating coupler);
  the only miss is one grating coupler → `unknown`.
- **Y-branch loss (3.126 dB)** is a *physics* check, not a metadata echo: a Y-branch
  splits power ~3 dB per arm. Recovering this from real Lumerical `.sparam` files
  confirms the amplitude→dB conversion and primary-path selection are correct.
- **Passivity (98%)** verifies parsed traces obey |S21| ≤ 0 dB. The ~2% that exceed
  it are under investigation (likely normalization in a few hybrid/contra-DC files).
- **GDS (99.4%)** shows the built-in GDSII reader handles real SiEPIC layouts.
- **482 duplicate groups** is a real finding: the PDK mirrors `source_data` across
  its `klayout/`, `Lumerical_EBeam_CML/`, and `opics/` trees.

Reproduce: `git clone --depth 1 https://github.com/SiEPIC/SiEPIC_EBeam_PDK` then
`simminer validate-external SiEPIC_EBeam_PDK` (no data is vendored into this repo).

## Tech stack (as built)

- **Core**: pure Python + Typer (no hard scientific dependency).
- **Optional extras**: `data` (numpy/pandas/pyarrow → Parquet), `viz` (plotly).
- GDSII is read/written by a built-in module — no `gdstk`/`gdspy` needed, which
  matters on Python 3.14 where those wheels may be unavailable.

## Known limitations / MVP boundaries

- Binary containers (`.fsp`, `.h5`, `.mat`, `.npz`, `.oas`) are discovered and
  inventoried but **not parsed** (337 `.mat` + 16 `.fsp` files in the PDK go
  unparsed today).
- The GDSII reader reads BOUNDARY elements in the stream but does **not follow
  SREF/AREF cell references**, so deeply hierarchical layouts may under-count
  polygons (flat SiEPIC cells parse fine — 99.4%).
- ~2% of real S-param traces fail the passivity check; needs root-causing
  (primary-path selection on hybrid/contra-DC devices).
- The HTML report uses static inline bars (no plotly charts yet).
- Constant parameters (e.g. fixed waveguide thickness) are still listed as
  features and depress coverage/diversity slightly.

## Next steps (post-MVP)

1. **Tier 3**: a reference `geometry → S21` surrogate trainer consuming the built
   datasets, reporting convergence/accuracy/latency (Benchmark 4 in [GOALS.md](GOALS.md)).
2. Root-cause the 2% passivity failures; refine INTERCONNECT primary-path selection.
3. Parse binary containers (`h5py` for `.h5`, `scipy.io` for `.mat`) behind the
   optional `data` extra.
4. Follow GDSII SREF/AREF references for hierarchical layouts.
5. Drop zero-variance columns from feature sets; add plotly charts to the report.
6. Geometry-embedding similarity to replace heuristic classification.
