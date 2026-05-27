"""Phase 1: artifact discovery.

Recursively scans a directory tree, classifies files, detects duplicates, and
groups files into logical simulation runs.
"""

from .scanner import DEFAULT_IGNORE_DIRS, run_key_for, scan

__all__ = ["scan", "run_key_for", "DEFAULT_IGNORE_DIRS"]
