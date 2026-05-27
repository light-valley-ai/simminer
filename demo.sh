#!/usr/bin/env bash
#
# demo.sh — end-to-end simminer walkthrough for live demos.
#
# Generates a synthetic photonics repo, then runs the full pipeline:
#   discovery -> metadata -> classification -> datasets -> readiness report.
#
# Usage:
#   ./demo.sh                 # run all steps, pausing between each (press Enter)
#   ./demo.sh --no-pause      # run straight through (good for recording / CI)
#   WORKDIR=/tmp/foo ./demo.sh   # override the scratch directory
#
set -euo pipefail

# --- config ---------------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="${WORKDIR:-/tmp/simminer_demo}"
EXAMPLE_REPO="$WORKDIR/example_repo"
DATASETS="$WORKDIR/datasets"
REPORT="$WORKDIR/report.html"

PAUSE=1
[[ "${1:-}" == "--no-pause" ]] && PAUSE=0

# --- helpers --------------------------------------------------------------
bold() { printf '\n\033[1;36m=== %s ===\033[0m\n' "$1"; }
step() {
  bold "$1"; shift
  printf '\033[2m$ %s\033[0m\n' "$*"
  [[ $PAUSE -eq 1 ]] && read -rp $'\033[2m(press Enter to run)\033[0m '
  "$@"
}

# --- locate the simminer CLI ----------------------------------------------
# Prefer (in order): explicit override, an external venv kept OUTSIDE any
# cloud-synced folder (see note below), the in-repo .venv, then $PATH.
#
# NOTE: on macOS, keeping .venv inside an iCloud/OneDrive-synced folder (e.g.
# ~/Documents) breaks editable installs — the sync daemon sets the hidden flag
# on the .pth file and Python 3.13+ skips hidden .pth files. So we default to
# ~/.venvs/simminer. See docs/DEMO.md for the full diagnosis.
EXTERNAL_VENV="${SIMMINER_VENV:-$HOME/.venvs/simminer}"
if [[ -n "${SIMMINER_BIN:-}" && -x "$SIMMINER_BIN" ]]; then
  SIMMINER="$SIMMINER_BIN"
elif [[ -x "$EXTERNAL_VENV/bin/simminer" ]]; then
  SIMMINER="$EXTERNAL_VENV/bin/simminer"
elif [[ -x "$REPO_ROOT/.venv/bin/simminer" ]]; then
  SIMMINER="$REPO_ROOT/.venv/bin/simminer"
elif command -v simminer >/dev/null 2>&1; then
  SIMMINER="$(command -v simminer)"
else
  echo "simminer not found. Set up a venv outside any synced folder:" >&2
  echo "  python3 -m venv ~/.venvs/simminer && ~/.venvs/simminer/bin/pip install -e \"$REPO_ROOT\"" >&2
  exit 1
fi

# Sanity-check it actually imports (editable installs can go stale, and a
# synced-folder venv can be silently broken by the hidden-.pth issue above).
if ! "$SIMMINER" version >/dev/null 2>&1; then
  echo "simminer ($SIMMINER) is installed but failing to import." >&2
  echo "If its venv lives under iCloud/OneDrive, recreate it elsewhere:" >&2
  echo "  python3 -m venv ~/.venvs/simminer && ~/.venvs/simminer/bin/pip install -e \"$REPO_ROOT\"" >&2
  echo "See docs/DEMO.md (macOS iCloud/OneDrive gotcha) for details." >&2
  exit 1
fi

echo "Using: $SIMMINER"
echo "Scratch dir: $WORKDIR"

# --- pipeline -------------------------------------------------------------
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR"

# 1. Synthesize a photonics repo (no real data needed to try it).
step "1. Generate synthetic photonics repo" \
  "$SIMMINER" gen-examples "$EXAMPLE_REPO"

# 2. Discover and inventory artifacts on disk.
step "2. Scan: discover & inventory artifacts" \
  "$SIMMINER" scan "$EXAMPLE_REPO"

# 3. Extract metadata, normalize geometry, classify components.
step "3. Analyze: metadata + classification" \
  "$SIMMINER" analyze "$EXAMPLE_REPO"

# 4. Build per-component, surrogate-ready datasets (geometry -> S-params).
step "4. Build surrogate-ready datasets" \
  "$SIMMINER" build-dataset "$EXAMPLE_REPO" -o "$DATASETS"

# 5. Readiness report (text summary + standalone HTML).
step "5. Readiness report (text + HTML)" \
  "$SIMMINER" report "$EXAMPLE_REPO" -o "$REPORT"

# 6. Validation / quality checks.
step "6. Validate parsing & dataset quality" \
  "$SIMMINER" validate "$EXAMPLE_REPO"

# 7. Benchmark against synthetic ground truth (proof it works).
step "7. Benchmark vs. synthetic ground truth" \
  "$SIMMINER" benchmark "$EXAMPLE_REPO"

# --- wrap-up --------------------------------------------------------------
bold "Demo complete"
echo "Artifacts:"
echo "  datasets : $DATASETS"
echo "  report   : $REPORT"
echo
echo "Open the HTML report:"
echo "  open $REPORT"
