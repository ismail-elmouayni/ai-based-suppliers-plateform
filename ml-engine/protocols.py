"""
protocols
=========
Protocol interfaces (structural typing contracts) for the four ML sub-modules.

Any class that implements the required methods automatically satisfies the
corresponding Protocol — no explicit inheritance is needed.  These types are
used for type-checker validation (mypy) and make the pipeline's dependencies
explicit and mockable in tests.
"""

from __future__ import annotations
from typing import Protocol
import pandas as pd


class IVendorResolver(Protocol):
    """Contract for vendor entity-resolution implementations."""
    def resolve(self, df: pd.DataFrame, run_id: int | None = None) -> pd.DataFrame: ...

class IVendorScorer(Protocol):
    """Contract for vendor-scoring implementations."""
    def score(self, df: pd.DataFrame, run_id: int) -> pd.DataFrame: ...


class IVendorClusterer(Protocol):
    """Contract for consolidation-clustering implementations."""
    def cluster(self, df: pd.DataFrame, run_id: int) -> tuple[pd.DataFrame, pd.DataFrame]: ...


class IAnomalyDetector(Protocol):
    """Contract for anomaly-detection implementations."""
    def detect(self, df: pd.DataFrame, run_id: int) -> pd.DataFrame: ...
