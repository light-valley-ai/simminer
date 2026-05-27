"""Phase 3: geometry normalization.

Parsers already emit canonical, unit-normalized geometry keys; this module
consolidates them and exposes numeric feature vectors for clustering and
dataset building.
"""

from .normalize import GEOMETRY_FIELDS, feature_vector, normalize

__all__ = ["normalize", "feature_vector", "GEOMETRY_FIELDS"]
