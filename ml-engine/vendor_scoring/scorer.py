"""
VendorScorer — composite vendor performance scoring.

For each (CanonicalVendorName, Category) pair with ≥ min_po_count POs:
  1. Compute raw signals: mean Saving_Pct, total Spend, specialization ratio
  2. Min-max normalize each signal across all scoreable pairs
  3. Weighted composite score on [0, 100]
  4. Assign performance band: GREEN / AMBER / RED / INSUFFICIENT_DATA
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

BAND_GREEN = "GREEN"
BAND_AMBER = "AMBER"
BAND_RED = "RED"
BAND_INSUFFICIENT = "INSUFFICIENT_DATA"


class VendorScorer:
    def __init__(self, config: dict):
        vs_cfg = config.get("vendor_scoring", {})
        self.w_saving = float(vs_cfg.get("saving_pct_weight", 0.50))
        self.w_spend = float(vs_cfg.get("spend_weight", 0.30))
        self.w_spec = float(vs_cfg.get("specialization_weight", 0.20))
        self.min_po_count = int(vs_cfg.get("min_po_count_for_scoring", 3))
        self.band_green_min = float(vs_cfg.get("band_green_min", 70))
        self.band_amber_min = float(vs_cfg.get("band_amber_min", 40))

        # Normalise weights to sum = 1
        total = self.w_saving + self.w_spend + self.w_spec
        if total > 0:
            self.w_saving /= total
            self.w_spend /= total
            self.w_spec /= total

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _minmax_norm(series: pd.Series) -> pd.Series:
        """Min-max normalise; returns 0.5 when min == max."""
        mn, mx = series.min(), series.max()
        if mx == mn:
            return pd.Series(0.5, index=series.index)
        return (series - mn) / (mx - mn)

    def _assign_band(self, score: float, po_count: int) -> str:
        if po_count < self.min_po_count:
            return BAND_INSUFFICIENT
        if score >= self.band_green_min:
            return BAND_GREEN
        if score >= self.band_amber_min:
            return BAND_AMBER
        return BAND_RED

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, df: pd.DataFrame, run_id: int) -> pd.DataFrame:
        """
        Score vendors from *df*.

        Required columns: CanonicalVendorName, Category, Saving_Pct, Spend, PO_Number.
        Returns a DataFrame ready for ai_output.VendorScores insertion.
        """
        if df.empty:
            logger.warning("score() called with empty DataFrame.")
            return pd.DataFrame()

        # Drop rows with NULL / None / "NULL" Category
        df = df[df["Category"].notna()].copy()
        null_sentinels = {"NULL", "None", "nan", ""}
        df = df[~df["Category"].astype(str).isin(null_sentinels)].copy()

        if df.empty:
            logger.warning("No scoreable rows after filtering NULL categories.")
            return pd.DataFrame()

        # --- Raw signals per (vendor, category) -----------------------
        agg = (
            df.groupby(["CanonicalVendorName", "Category"])
            .agg(
                RawSavingPct=("Saving_Pct", "mean"),
                RawTotalSpend=("Spend", "sum"),
                POCount=("PO_Number", "count"),
            )
            .reset_index()
        )

        # Specialization: vendor's spend in category / vendor's total spend
        vendor_total = df.groupby("CanonicalVendorName")["Spend"].sum().rename("VendorTotalSpend")
        agg = agg.join(vendor_total, on="CanonicalVendorName")
        agg["RawSpecialization"] = (
            agg["RawTotalSpend"] / agg["VendorTotalSpend"].replace(0, np.nan)
        ).fillna(0.0)

        # Fill NaN saving pcts with 0
        agg["RawSavingPct"] = agg["RawSavingPct"].fillna(0.0)

        # --- Scoreable subset -----------------------------------------
        scoreable = agg[agg["POCount"] >= self.min_po_count].copy()
        insufficient = agg[agg["POCount"] < self.min_po_count].copy()

        rows = []

        if not scoreable.empty:
            # Min-max normalise
            scoreable["SavingPctNorm"] = self._minmax_norm(scoreable["RawSavingPct"])
            scoreable["SpendNorm"] = self._minmax_norm(scoreable["RawTotalSpend"])
            scoreable["SpecializationNorm"] = self._minmax_norm(scoreable["RawSpecialization"])

            scoreable["CompositeScore"] = (
                scoreable["SavingPctNorm"] * self.w_saving
                + scoreable["SpendNorm"] * self.w_spend
                + scoreable["SpecializationNorm"] * self.w_spec
            ) * 100.0

            scoreable["CompositeScore"] = scoreable["CompositeScore"].round(2).clip(0, 100)
            scoreable["PerformanceBand"] = scoreable.apply(
                lambda r: self._assign_band(r["CompositeScore"], r["POCount"]), axis=1
            )

            for _, row in scoreable.iterrows():
                rows.append(self._to_output_row(row, run_id))

        # Insufficient data rows
        for _, row in insufficient.iterrows():
            rows.append(
                {
                    "RunId": run_id,
                    "CanonicalVendorName": row["CanonicalVendorName"],
                    "Category": row["Category"],
                    "CompositeScore": 0.0,
                    "PerformanceBand": BAND_INSUFFICIENT,
                    "SavingPctNorm": None,
                    "SpendNorm": None,
                    "SpecializationNorm": None,
                    "RawSavingPct": row["RawSavingPct"],
                    "RawTotalSpend": row["RawTotalSpend"],
                    "RawSpecialization": row["RawSpecialization"],
                    "POCount": int(row["POCount"]),
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
            "CanonicalVendorName": row["CanonicalVendorName"],
            "Category": row["Category"],
            "CompositeScore": float(row["CompositeScore"]),
            "PerformanceBand": row["PerformanceBand"],
            "SavingPctNorm": float(row["SavingPctNorm"]),
            "SpendNorm": float(row["SpendNorm"]),
            "SpecializationNorm": float(row["SpecializationNorm"]),
            "RawSavingPct": float(row["RawSavingPct"]),
            "RawTotalSpend": float(row["RawTotalSpend"]),
            "RawSpecialization": float(row["RawSpecialization"]),
            "POCount": int(row["POCount"]),
        }
