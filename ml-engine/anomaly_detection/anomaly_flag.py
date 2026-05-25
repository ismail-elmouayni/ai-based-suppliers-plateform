"""
Anomaly detection domain types for the ML pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import pandas as pd

from core.raw_data_processing import RawDataProcessing
from data_source_columns import DataSourceColumns


class Severity(StrEnum):
    """Anomaly severity levels.  ``StrEnum`` guarantees ``str(member) == member.value``
    across all Python versions — backward-compatible with DB writes and tests."""

    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


@dataclass
class AnomalyFlag:
    """Typed result produced by AnomalyDetector for a single anomalous PO."""

    # --- Column name constants (equal to their field names) ---
    RUN_ID            = "run_id"
    SOURCE_RECORD_ID  = "source_record_id"
    PO_NUMBER         = "po_number"
    CANONICAL_VENDOR  = "canonical_vendor_name"
    CATEGORY          = "category"
    ORIGINAL_SPEND    = "original_spend"
    SPEND             = "spend"
    SPEND_GAP         = "spend_gap"
    ANOMALY_SCORE     = "anomaly_score"
    Z_SCORE           = "z_score"
    SEVERITY          = "severity"
    REASON_STRING     = "reason_string"

    # --- Fields ---
    run_id:                int
    source_record_id:      int | None
    po_number:             str | None
    canonical_vendor_name: str
    category:              str | None
    original_spend:        float | None
    spend:                 float | None
    spend_gap:             float
    anomaly_score:         float
    z_score:               float
    severity:              Severity
    reason_string:         str

    @classmethod
    def from_detection(cls, run_id: int, row: pd.Series, spend_gap: float,
        anomaly_score: float,
        z_score: float,
        severity: Severity,
    ) -> AnomalyFlag:
        """Construct an AnomalyFlag from a detected anomalous PO row."""
        
        vendor   = str(row.get(DataSourceColumns.CANONICAL_VENDOR, ""))
        raw_cat  = str(row.get(DataSourceColumns.CATEGORY) or "")
        category = raw_cat if raw_cat not in RawDataProcessing.NULL_VALUES else None

        original_spend = float(row.get(DataSourceColumns.ORIGINAL_SPEND) or 0)
        pct  = (spend_gap / abs(original_spend) * 100) if original_spend != 0 else 0.0
        direction = "exceeds original" if spend_gap > 0 else "below original"
        cat_str   = f"{vendor} - {category}" if category else vendor

        reason = (
            f"Spend {direction} by {abs(pct):.1f}% "
            f"({abs(spend_gap):.2f} absolute); "
            f"{abs(z_score):.1f}\u03c3 above {cat_str} mean gap"
        )

        return cls(
            run_id=run_id,
            source_record_id=row.get(DataSourceColumns.ID),
            po_number=row.get(DataSourceColumns.PURCHASE_ORDERS_NUMBER),
            canonical_vendor_name=vendor,
            category=category,
            original_spend=row.get(DataSourceColumns.ORIGINAL_SPEND),
            spend=row.get(DataSourceColumns.SPEND),
            spend_gap=spend_gap,
            anomaly_score=round(anomaly_score, 6),
            z_score=round(z_score, 4),
            severity=severity,
            reason_string=reason,
        )
