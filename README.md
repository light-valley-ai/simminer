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

### What it does to your data

`simminer` takes a pile of inconsistently-named files and turns it into clean,
per-component tables plus a readiness verdict:

```
  messy archive on disk                       structured, surrogate-ready output
  ─────────────────────                       ──────────────────────────────────
  runs/
    yj_w500_g80.lsf      ┐                     y_splitters.parquet
    yj_w500_g80.gds      │   ┌────────────┐      ┌──────────┬──────────┬─────────┐
    yj_w500.s2p          ├─► │  simminer  │ ─►   │ width_nm │ gap_nm   │  S21 …  │
    Lc10um_gap200.csv    │   │  pipeline  │      ├──────────┼──────────┼─────────┤
    Lc10um_gap200.gds    │   └────────────┘      │   500    │   80     │ -3.1 dB │
    copy_of_yj.s2p (dup) ┘          │            │   …      │   …      │   …     │
                                    │            └──────────┴──────────┴─────────┘
                                    ▼            + readiness report (HTML):
                            features ⨝ targets     "y_splitter: Medium (0.46),
                            per component           use a Gaussian Process,
                                                    ~81 compute-hrs saved"
```

Want to see it run, with a talking point for every stage? See the
**[demo walkthrough](docs/DEMO.md)** (`./demo.sh`).

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

Or run all of it at once with the guided demo:

```bash
./demo.sh            # add --no-pause to run straight through
```

### Example output

What `analyze` and `report` print on the synthetic repo:

```text
$ simminer analyze ./example_repo
Analyzed ./example_repo
  runs: 66
  components:
    directional_coupler    29
    y_splitter             36
    unknown                 1

$ simminer report ./example_repo -o report.html
Surrogate readiness:
  [y_splitter]
     runs=36 usable=36  features=branch_angle_deg, taper_length_um, thickness_nm, width_nm
     coverage=0.275  density=0.333  diversity=0.385  output_stability=1.0
     readiness=0.457 (Medium)  model=Gaussian Process / Kriging (data-efficient)
     est. compute savings: 81.0 hrs
       ! Sparse parameter coverage; sweep underexplored ranges.
```

The readiness score tells you **whether the data is good enough to train a
surrogate** — and what's missing — *before* you spend the compute.

## Validated on real data

Beyond synthetic tests, simminer is validated against the open
[SiEPIC EBeam PDK](https://github.com/SiEPIC/SiEPIC_EBeam_PDK), which is wired
in as a git submodule under `test_data/SiEPIC_EBeam_PDK`:

```bash
# fetch the PDK alongside the repo
git clone --recurse-submodules <this-repo>
# or, if you already cloned without submodules:
git submodule update --init --depth 1

simminer validate-external test_data/SiEPIC_EBeam_PDK
#   classification: 99.7% accuracy on 323 labeled runs
#   Y-branch loss : mean 3.126 dB (within 2.5-5 dB: 100.0%, n=56)
#   GDS reader    : 99.4% of 172 layouts yielded polygons
```

Add `--json` or `--html` to emit the full report instead of the summary, and
`-o PATH` to write it to a file (the format is inferred from the suffix if no
flag is given):

```bash
simminer validate-external test_data/SiEPIC_EBeam_PDK --html -o validation.html
simminer validate-external test_data/SiEPIC_EBeam_PDK --json -o validation.json
```

The Y-branch ~3 dB split is a physics check (not a metadata echo), so it
independently confirms the S-parameter parser. See
[`docs/STATUS.md`](docs/STATUS.md#tier-2--validated-on-real-data-siepic-ebeam-pdk)
for the full breakdown and methodology.

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
| Geometry  | `.gds` (built-in reader), geometry `.json`, **filenames** (`gap=80nm`, `Lc=10um`) | `.oas`                  |
| Results   | `.s2p` (Touchstone), **`.sparam`/`.dat` (Lumerical INTERCONNECT)**, `.csv` S-params/spectra, Meep flux `.csv` | `.h5`, `.mat`, `.npz` |

## Development

```bash
pip install -e ".[dev]"
pytest                      # run the test suite
```

## License

MIT — see [LICENSE](LICENSE).
