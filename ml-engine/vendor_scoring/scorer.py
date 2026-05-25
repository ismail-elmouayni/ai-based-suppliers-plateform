"""
VendorScorer — composite vendor performance scoring.

For each (CanonicalVendorName, Category) pair with ≥ min_purchase_count purchase orders:
  1. Compute raw signals: mean Saving_Pct, total Spend, specialization ratio
  2. Min-max normalize each signal across all scoreable pairs
  3. Weighted composite score on [0, 100]
  4. Assign performance band: GREEN / AMBER / RED / INSUFFICIENT_DATA
"""

from __future__ import annotations
import logging
from enum import StrEnum

import numpy as np
import pandas as pd

from config_types import VendorScoringConfig
from data_source_columns import DataSourceColumns

logger = logging.getLogger(__name__)


class PerformanceBand(StrEnum):
    """Vendor performance bands.  ``StrEnum`` guarantees ``str(member) == member.value``
    across all Python versions — backward-compatible with DB writes and tests."""

    GREEN        = "GREEN"
    AMBER        = "AMBER"
    RED          = "RED"
    INSUFFICIENT = "INSUFFICIENT_DATA"



class VendorScorer:
    def __init__(self, config: VendorScoringConfig) -> None:
        self.saving_weight          = config.saving_pct_weight
        self.spend_weight           = config.spend_weight
        self.specialization_weight  = config.specialization_weight
        self.min_purchase_count       = config.min_purchase_count
        self.band_green_min         = config.band_green_min
        self.band_amber_min         = config.band_amber_min


    @staticmethod
    def _normalize(series: pd.Series) -> pd.Series:
        """Min-max normalise, making series value betsween 0 and 1; returns 0.5 when min == max."""
        mn, mx = series.min(), series.max()
        if mx == mn:
            return pd.Series(0.5, index=series.index)
        
        return (series - mn) / (mx - mn)

    def _assign_performance_band(self, score: float, purchase_count: int) -> PerformanceBand:
        """Assign performance band based on composite score and purchase count."""
        if purchase_count < self.min_purchase_count:
            return PerformanceBand.INSUFFICIENT
        if score >= self.band_green_min:
            return PerformanceBand.GREEN
        if score >= self.band_amber_min:
            return PerformanceBand.AMBER
        
        return PerformanceBand.RED


    def score(self, data_frame: pd.DataFrame, run_id: int) -> pd.DataFrame:
        """
        Score vendors from *data_frame*.

        Required columns: CanonicalVendorName, Category, Saving_Pct, Spend, PO_Number.
        (See DataSourceColumns for canonical column name constants.)
        Returns a DataFrame ready for ai_output.VendorScores insertion.
        """
        if data_frame.empty:
            logger.warning("score() called with empty DataFrame.")
            return pd.DataFrame()

        # Drop rows with NULL / None / "NULL" Category
        data_frame = data_frame[data_frame[DataSourceColumns.CATEGORY].notna()].copy()
        null_sentinels = {"NULL", "None", "nan", ""}
        data_frame = data_frame[~data_frame[DataSourceColumns.CATEGORY].astype(str).isin(null_sentinels)].copy()

        if data_frame.empty:
            logger.warning("No scoreable rows after filtering NULL categories.")
            return pd.DataFrame()

        # --- Raw signals per (vendor, category) -----------------------
        agg = (
            data_frame.groupby([DataSourceColumns.CANONICAL_VENDOR, DataSourceColumns.CATEGORY])
            .agg(
                RawSavingPct=(DataSourceColumns.SAVING_PERCENT, "mean"),
                RawTotalSpend=(DataSourceColumns.SPEND, "sum"),
                PurchaseCount=(DataSourceColumns.PURCHASE_ORDERS_NUMBER, "count"),
            )
            .reset_index()
        )

        # Specialization: vendor's spend in category / vendor's total spend
        vendor_total = data_frame.groupby(DataSourceColumns.CANONICAL_VENDOR)[DataSourceColumns.SPEND].sum().rename("VendorTotalSpend")
        agg = agg.join(vendor_total, on=DataSourceColumns.CANONICAL_VENDOR)
        agg["RawSpecialization"] = (
            agg["RawTotalSpend"] / agg["VendorTotalSpend"].replace(0, np.nan)
        ).fillna(0.0)

        # Fill NaN saving pcts with 0
        agg["RawSavingPct"] = agg["RawSavingPct"].fillna(0.0)

        # --- Scoreable subset -----------------------------------------
        scoreable = agg[agg["PurchaseCount"] >= self.min_purchase_count].copy()
        insufficient = agg[agg["PurchaseCount"] < self.min_purchase_count].copy()

        rows = []

        if not scoreable.empty:
            # Min-max normalise
            scoreable["SavingPctNorm"] = self._normalize(scoreable["RawSavingPct"])
            scoreable["SpendNorm"] = self._normalize(scoreable["RawTotalSpend"])
            scoreable["SpecializationNorm"] = self._normalize(scoreable["RawSpecialization"])

            scoreable["CompositeScore"] = (
                scoreable["SavingPctNorm"] * self.saving_weight
                + scoreable["SpendNorm"] * self.spend_weight
                + scoreable["SpecializationNorm"] * self.specialization_weight
            ) * 100.0

            scoreable["CompositeScore"] = scoreable["CompositeScore"].round(2).clip(0, 100)
            scoreable["PerformanceBand"] = scoreable.apply(
                lambda r: self._assign_performance_band(r["CompositeScore"], r["PurchaseCount"]), axis=1
            )

            for _, row in scoreable.iterrows():
                rows.append(self._to_output_row(row, run_id))

        # Insufficient data rows
        for _, row in insufficient.iterrows():
            rows.append(
                {
                    "RunId": run_id,
                    DataSourceColumns.CANONICAL_VENDOR: row[DataSourceColumns.CANONICAL_VENDOR],
                    DataSourceColumns.CATEGORY: row[DataSourceColumns.CATEGORY],
                    "CompositeScore": 0.0,
                    "PerformanceBand": PerformanceBand.INSUFFICIENT,
                    "SavingPctNorm": None,
                    "SpendNorm": None,
                    "SpecializationNorm": None,
                    "RawSavingPct": row["RawSavingPct"],
                    "RawTotalSpend": row["RawTotalSpend"],
                    "RawSpecialization": row["RawSpecialization"],
                    "PurchaseCount": int(row["PurchaseCount"]),
                }
            )

        result = pd.DataFrame(rows)
        logger.info(
            f"Scoring complete: {len(scoreable)} scored, "
            f"{len(insufficient)} insufficient_data pairs."
        )
        return result

    @staticmethod
    def _to_output_row(row: pd.Series, run_id: int) -> dict:
        return {
            "RunId": run_id,
            DataSourceColumns.CANONICAL_VENDOR: row[DataSourceColumns.CANONICAL_VENDOR],
            DataSourceColumns.CATEGORY: row[DataSourceColumns.CATEGORY],
            "CompositeScore": float(row["CompositeScore"]),
            "PerformanceBand": row["PerformanceBand"],
            "SavingPctNorm": float(row["SavingPctNorm"]),
            "SpendNorm": float(row["SpendNorm"]),
            "SpecializationNorm": float(row["SpecializationNorm"]),
            "RawSavingPct": float(row["RawSavingPct"]),
            "RawTotalSpend": float(row["RawTotalSpend"]),
            "RawSpecialization": float(row["RawSpecialization"]),
            "PurchaseCount": int(row["PurchaseCount"]),
        }
