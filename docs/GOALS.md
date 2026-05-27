# Goals & Vision

## Vision

Simulation Data Miner is an open-source platform for discovering, structuring,
validating, and operationalizing historical photonics simulation data for
AI-assisted design workflows.

It transforms fragmented simulation artifacts into:

- searchable datasets
- reusable design intelligence
- surrogate-ready training corpora
- optimization-ready metadata layers

**The goal is not replacing physics solvers — it is enabling AI-native photonics
workflows on top of existing engineering data.**

## The problem

Most silicon photonics organizations accumulate years of FDTD simulations,
parameter sweeps, GDS variants, monitor outputs, S-parameter exports, and
optimization scripts. But this data usually lives as engineer-local folders with
inconsistent naming, duplicated runs, undocumented geometries, and disconnected
outputs. As a result:

- historical knowledge is lost
- simulations get rerun repeatedly
- surrogate-model training is difficult
- optimization workflows lack structured datasets

## Core goals

1. **Discover** simulation artifacts automatically
2. **Parse & normalize** engineering metadata
3. **Extract** geometry ↔ output relationships
4. **Cluster** related simulation families
5. **Generate** surrogate-readiness reports
6. **Build** reusable datasets
7. **Provide** hooks for future AI workflows

## Strategic positioning

This project is **infrastructure for AI-native photonics workflows**, not "AI
replacing photonics engineers." That framing is stronger both technically and
commercially.

## Roadmap (post-MVP)

| Phase | Capability                         | Direction                          |
|-------|------------------------------------|------------------------------------|
| 2     | Surrogate training pipelines       | `geometry → optical prediction`    |
| 3     | Inverse design agents              | `goal → candidate geometry`        |
| 4     | Physics-aware validation           | Maxwell residual verification      |
| 5     | Interactive design studio          | Real-time exploration workflows    |

## How we prove it works (benchmarks)

1. **Discovery accuracy** — precision/recall of artifact identification.
2. **Metadata extraction accuracy** — field-level recovery vs. source scripts.
3. **Clustering accuracy** — manual engineer validation of component grouping.
4. **Surrogate readiness** — train a simple `geometry → S21` model; report
   convergence, accuracy, inference latency.
5. **Engineering time saved** — reduction in search time, reruns, duplicate
   simulations, and dataset-prep effort.
