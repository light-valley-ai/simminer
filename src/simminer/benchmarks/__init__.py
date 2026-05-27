"""Benchmarks: measurable proof that the pipeline works.

Uses the synthetic generator (whose ground truth is encoded in file paths) to
score the pipeline on the metrics from the project plan:

* Benchmark 1 -- discovery (artifact recall, duplicate detection)
* Benchmark 2 -- metadata extraction accuracy (recovered vs. encoded params)
* Benchmark 3 -- component classification accuracy
"""

from .run import run_benchmarks

__all__ = ["run_benchmarks"]
