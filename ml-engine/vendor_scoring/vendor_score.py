"""
Scoring domain types for the vendor scoring pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from data_source_columns import DataSourceColumns


class PerformanceBand(StrEnum):
    """Vendor performance bands.  ``StrEnum`` guarantees ``str(member) == member.value``
    across all Python versions — backward-compatible with DB writes and tests."""

    GREEN        = "GREEN"
    AMBER        = "AMBER"
    RED          = "RED"
    INSUFFICIENT = "INSUFFICIENT_DATA"


@dataclass
class VendorScore:
    """Typed result produced by VendorScorer for a single (vendor, category) pair."""

    # --- Column name constants (equal to their field names) ---
    COMPOSITE_SCORE            = "composite_score"
    PERFORMANCE_BAND           = "performance_band"
    SAVING_PERCENT_NORM            = "saving_pct_norm"
    SPEND_NORM                 = "spend_norm"
    SPECIALIZATION_NORM        = "specialization_norm"
    RAW_AVERAGE_SAVING_PERCENT = "raw_average_saving_percent"
    RAW_TOTAL_SPEND            = "raw_total_spend"
    RAW_SPECIALIZATION         = "raw_specialization"
    RAW_PURCHASE_COUNT         = "raw_purchase_count"

    # --- Fields ---
    run_id:                      int
    canonical_vendor_name:       str
    category:                    str
    composite_score:             float
    performance_band:            PerformanceBand
    saving_pct_norm:             float | None
    spend_norm:                  float | None
    specialization_norm:         float | None
    raw_average_saving_percent:  float
    raw_total_spend:             float
    raw_specialization:          float
    raw_purchase_count:          int

    @classmethod
    def from_series(cls, run_id: int, row: pd.Series) -> VendorScore:
        """Construct a VendorScore from an aggregated scorer DataFrame row."""
        return cls(
            run_id=run_id,
            canonical_vendor_name=row[DataSourceColumns.CANONICAL_VENDOR],
            category=row[DataSourceColumns.CATEGORY],
            composite_score=float(row[cls.COMPOSITE_SCORE]),
            performance_band=row[cls.PERFORMANCE_BAND],
            saving_pct_norm=float(row[cls.SAVING_PERCENT_NORM]),
            spend_norm=float(row[cls.SPEND_NORM]),
            specialization_norm=float(row[cls.SPECIALIZATION_NORM]),
            raw_average_saving_percent=float(row[cls.RAW_AVERAGE_SAVING_PERCENT]),
            raw_total_spend=float(row[cls.RAW_TOTAL_SPEND]),
            raw_specialization=float(row[cls.RAW_SPECIALIZATION]),
            raw_purchase_count=int(row[cls.RAW_PURCHASE_COUNT]),
        )
    
    @classmethod
    def create_insufficient_data(cls, run_id: int, row : pd.Series) -> VendorScore:
        """Factory method for creating an INSUFFICIENT_DATA VendorScore."""
        return cls(
            run_id=run_id,
            canonical_vendor_name=row[DataSourceColumns.CANONICAL_VENDOR],
            category=row[DataSourceColumns.CATEGORY],
            composite_score=0.0,
            performance_band=PerformanceBand.INSUFFICIENT,
            saving_pct_norm=None,
            spend_norm=None,
            specialization_norm=None,
            raw_average_saving_percent=float(row[cls.RAW_AVERAGE_SAVING_PERCENT]),
            raw_total_spend=float(row[cls.RAW_TOTAL_SPEND]),
            raw_specialization=float(row[cls.RAW_SPECIALIZATION]),
            raw_purchase_count=int(row[cls.RAW_PURCHASE_COUNT]),
        )
            