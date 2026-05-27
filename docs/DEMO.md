# Demo Walkthrough (`demo.sh`)

`demo.sh` is the end-to-end live demo. It synthesizes a fake photonics repo and
runs the **whole `simminer` pipeline** against it — discovery → metadata →
classification → datasets → readiness report → validation → benchmark — so you
can show the product working in ~90 seconds with no real data and no setup.

This doc explains **what each step does** and gives a **talking point** for each
(use it as a presenter script). It also documents the one environment gotcha
that bites on macOS.

## Why build this?

Open the demo with the problem, not the tool. Silicon photonics teams accumulate
**years** of FDTD runs, parameter sweeps, GDS variants, and S-parameter exports —
and almost all of it rots in engineer-local folders with inconsistent naming, no
schema, and no link between a geometry and the output it produced. The cost is
concrete:

- **Knowledge walks out the door.** When an engineer leaves, their sweeps become
  unreadable files nobody can interpret or trust.
- **The same simulation gets run again and again.** FDTD is expensive; teams burn
  compute-days re-deriving results they already have on disk somewhere.
- **Surrogate / ML efforts stall at step zero.** You can't train a
  `geometry → optics` model without a clean, labeled corpus — and assembling one
  by hand from scattered files is weeks of grunt work, so it never happens.
- **Optimization and design-space exploration have no structured data to stand
  on.** The inputs simply aren't in a usable shape.

This is the bottleneck **in front of** every AI-for-photonics ambition. The
industry is racing toward surrogate models and inverse design, but those need a
validated data layer that doesn't exist yet. `simminer` builds that layer: it
turns the dead archive into a searchable inventory and `geometry → S-parameter`
datasets, and — critically — it scores **whether you have enough data to train a
surrogate at all**, so teams stop guessing.

Strategically, this is **infrastructure for AI-native photonics workflows**, not
"AI replacing photonics engineers." That framing is both more honest and more
defensible: every team already has the data, nobody has the layer that makes it
usable, and that layer is the prerequisite for Phases 2–5 (surrogate training,
inverse design, physics-aware validation). See [`GOALS.md`](GOALS.md) for the
full vision and roadmap.

> **Opening talking point:** "Every photonics team is sitting on years of
> simulation data they can't use, re-running expensive solves because they can't
> find or trust what they already have. We don't replace the physics solver — we
> make the data it already produced usable by AI. That data layer is the thing
> standing between these teams and surrogate models, and nobody's built it."

## Running it

```bash
./demo.sh                 # interactive — pauses before each step (press Enter)
./demo.sh --no-pause      # straight through (good for recording / CI)
WORKDIR=/tmp/foo ./demo.sh   # override the scratch dir (default /tmp/simminer_demo)
```

The script locates the CLI in this order — `$SIMMINER_BIN` →
`$SIMMINER_VENV/bin/simminer` (default `~/.venvs/simminer`) → in-repo
`.venv/bin/simminer` → `$PATH` — sanity-checks that it imports, wipes the
scratch dir, and runs the seven steps below. Artifacts land in `$WORKDIR`
(`datasets/`, `report.html`).

> The external `~/.venvs/simminer` is preferred **on purpose**: a venv inside an
> iCloud/OneDrive-synced folder gets silently broken (see the gotcha below), so
> the recommended setup keeps the venv outside the synced tree.

## Prerequisite: the editable install must actually import

Recommended setup — venv **outside** the cloud-synced repo (this is what
`demo.sh` picks up by default):

```bash
python3 -m venv ~/.venvs/simminer
~/.venvs/simminer/bin/pip install -e ".[all]"
./demo.sh        # finds ~/.venvs/simminer automatically
```

An in-repo `.venv` also works *if the repo isn't under iCloud/OneDrive*:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
```

### ⚠️ macOS + iCloud/OneDrive gotcha (read this if the demo says "failing to import")

If `demo.sh` aborts with:

```
simminer is installed but failing to import. Reinstall with: ...
```

…and reinstalling **doesn't** fix it, the cause is almost certainly **cloud
sync**, not a broken install. This repo lives under `~/Documents`, which iCloud
Drive (and/or OneDrive) syncs. The sync daemon sets the macOS **`UF_HIDDEN`**
flag on files — including the editable-install path file
`.venv/.../site-packages/_editable_impl_simminer.pth`.

**Python 3.13+ deliberately skips any `.pth` file with the hidden flag set**
(`site.addpackage` checks `st_flags & UF_HIDDEN`). So the line that adds `src/`
to `sys.path` is never processed, and `import simminer` fails — even though the
package is installed correctly.

Diagnose:

```bash
ls -lO .venv/lib/python*/site-packages/_editable_impl_simminer.pth   # shows "hidden"
```

Clearing the flag works only for a second — the sync daemon re-applies it
immediately (you'll also see a tell-tale `_editable_impl_simminer 2.pth` sync
conflict copy). Durable fixes, best first:

1. **Create the venv outside the synced folder** (recommended — venvs should
   never live in iCloud/OneDrive anyway):
   ```bash
   python -m venv ~/.venvs/simminer && ~/.venvs/simminer/bin/pip install -e ".[all]"
   ```
2. **Exclude `.venv` from sync** (e.g. rename to `.venv.nosync`, or mark the
   folder excluded in the sync client) and reinstall.
3. **Quick workaround** to run the demo right now without touching the install —
   put the source tree on the path directly, bypassing the `.pth`:
   ```bash
   PYTHONPATH="$PWD/src" ./demo.sh --no-pause
   ```

> Note: a stale/garbled `PYTHONPATH` in your shell (e.g. leftover Spark paths) is
> harmless here — it does not cause this failure. The hidden `.pth` flag does.

## The seven steps

Numbers below are from a representative run on the synthetic repo (64 generated
runs); your exact counts will match since the generator is deterministic per run.

### 1. `gen-examples` — synthesize a photonics repo

Writes a realistic mess of artifacts to disk: Lumerical `.lsf` scripts, GDSII
layouts, Touchstone/CSV S-parameters, Meep JSON, with inconsistent naming and a
duplicate — so the demo needs **no proprietary data**.

```
Generated 64 synthetic runs: y_splitter 33, directional_coupler 28, meep_y_splitter 3
```

> **Talking point:** "Every team's simulation folder looks like this — scattered
> files, no schema. We generate a stand-in so you can try the tool on your laptop
> in 30 seconds without exposing any real IP."

### 2. `scan` — discover & inventory

Walks the tree, type-IDs every file, groups files into **logical runs**, and
detects duplicates. Pure stdlib — no heavy deps.

```
files: 196  runs: 66  dupes: 1 group
by kind: geometry 36, result 99, simulation 61
by filetype: .csv 69, .gds 33, .lsf 61, .s2p 29, .json 3, .txt 1
```

> **Talking point:** "196 loose files collapse into 66 logical runs, and we
> automatically flag the duplicate. This is the 'I can finally see what we have'
> moment — searchable inventory from a pile of folders."

### 3. `analyze` — metadata extraction + classification

Runs the per-format parsers, mines parameters out of **filenames**
(`gap=80nm`, `Lc=10um`), normalizes geometry units, and clusters each run into a
component class.

```
runs: 66  →  y_splitter 36, directional_coupler 29, unknown 1
```

> **Talking point:** "We recover engineering metadata even when it only exists in
> a filename, and classify components automatically. The one 'unknown' is honest —
> we don't fabricate a label we can't justify."

### 4. `build-dataset` — surrogate-ready datasets

Joins each component's geometry features to its S-parameter targets and writes
one **Parquet** table per component (CSV fallback without the `data` extra).

```
directional_couplers.parquet  28 rows  (4 features, 5 targets)
y_splitters.parquet           36 rows  (4 features, 8 targets)
```

> **Talking point:** "This is the payload for ML. `geometry → S-parameters` in a
> clean tabular format — the exact shape you need to train a surrogate. We turned
> archive sludge into a training corpus."

### 5. `report` — readiness report (text + HTML)

Scores each component for **surrogate readiness** (coverage, density, diversity,
output stability), recommends a model class, and estimates compute saved. Writes
a standalone HTML report.

```
[y_splitter]          readiness=0.457 (Medium)  → Gaussian Process / Kriging  · est. 81 hrs saved
[directional_coupler] readiness=0.464 (Medium)  → Gaussian Process / Kriging  · est. 56 hrs saved
  ! Sparse parameter coverage; sweep underexplored ranges.
```

> **Talking point:** "The killer feature: before anyone wastes a week training, we
> tell them whether the data is *good enough* — and exactly what's missing
> ('sparse coverage, sweep these ranges'). It even quantifies the compute hours a
> surrogate would save."

### 6. `validate` — parsing & dataset quality

Self-check on the pipeline: parse rate, geometry coverage, output coverage,
duplicate ratio. Gates the demo with a PASS/FAIL.

```
Validation: PASS
  parse_rate 0.985  geometry_rate 0.97  output_rate 0.985  duplicate_ratio 0.01
```

> **Talking point:** "We hold ourselves to a quality bar. 98.5% parse rate isn't a
> marketing number — it's a gate the tool reports on every run."

### 7. `benchmark` — vs. synthetic ground truth

Because the repo is synthetic, we **know the true labels and metadata**, so we
can measure accuracy directly — proof, not vibes.

```
discovery: 196 files, 66 runs, dup-detection OK
classification accuracy : 100.0%  (n=65)
metadata extraction acc :  98.8%  (n=166 fields)
```

> **Talking point:** "Same pipeline, scored against ground truth: 100%
> classification, 98.8% metadata extraction. And it's not just synthetic — see the
> SiEPIC EBeam PDK validation in the README for the same numbers on real public
> data (99.7% classification, Y-branch ~3 dB physics check)."

## One-line pitch

> "`simminer` turns a team's years of scattered FDTD/GDS/S-parameter files into a
> searchable inventory and clean `geometry → optics` datasets — and tells you
> whether you have enough data to train a surrogate before you spend the compute."

See [`GOALS.md`](GOALS.md) for the vision/roadmap and
[`ARCHITECTURE.md`](ARCHITECTURE.md) for how the stages fit together.
</content>
</invoke>
