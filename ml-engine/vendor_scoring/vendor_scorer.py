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

import numpy as np
import pandas as pd

from config_types import VendorScoringConfig
from core.raw_data_processing import RawDataProcessing
from core.series_processing import normalize
from data_source_columns import DataSourceColumns
from vendor_scoring.vendor_score import PerformanceBand, VendorScore

logger = logging.getLogger(__name__)


class VendorScorer:
    def __init__(self, config: VendorScoringConfig) -> None:
        self.saving_weight          = config.saving_pct_weight
        self.spend_weight           = config.spend_weight
        self.specialization_weight  = config.specialization_weight
        self.min_purchase_count     = config.min_purchase_count
        self.band_green_min         = config.band_green_min
        self.band_amber_min         = config.band_amber_min

    
    def _assign_performance_band(self, score: float, purchase_count: int) -> PerformanceBand:
        """Assign performance band based on composite score and purchase count."""
        if purchase_count < self.min_purchase_count:
            return PerformanceBand.INSUFFICIENT
        if score >= self.band_green_min:
            return PerformanceBand.GREEN
        if score >= self.band_amber_min:
            return PerformanceBand.AMBER
        
        return PerformanceBand.RED

    def score(self, data_frame: pd.DataFrame, run_id: int) -> list[VendorScore]:
        """
        Score vendors from *data_frame*.

        Required columns: CanonicalVendorName, Category, Saving_Pct, Spend, PO_Number.
        (See DataSourceColumns for canonical column name constants.)
        Returns a DataFrame ready for ai_output.VendorScores insertion.
        """
        if data_frame.empty:
            logger.warning("score() called with empty DataFrame.")
            return []

        data_frame = RawDataProcessing.drop_null_column(data_frame, DataSourceColumns.CATEGORY)
        if data_frame.empty:
            logger.warning("No scoreable rows after filtering NULL categories.")
            return []

        aggregatedRawData = (
                data_frame.groupby([DataSourceColumns.CANONICAL_VENDOR, DataSourceColumns.CATEGORY])
                          .agg(**{  
                                    VendorScore.RAW_AVERAGE_SAVING_PERCENT: (DataSourceColumns.SAVING_PERCENT, "mean"),
                                    VendorScore.RAW_TOTAL_SPEND:            (DataSourceColumns.SPEND, "sum"),
                                    VendorScore.RAW_PURCHASE_COUNT:         (DataSourceColumns.PURCHASE_ORDERS_NUMBER, "count"),
                                })
                            .reset_index())

        # cross categories vendor total spend
        vendor_total_spend = data_frame.groupby(DataSourceColumns.CANONICAL_VENDOR)[DataSourceColumns.SPEND].sum().rename("vendor_total_spend")
        aggregatedRawData = aggregatedRawData.join(vendor_total_spend, on=DataSourceColumns.CANONICAL_VENDOR)
        
        aggregatedRawData[VendorScore.RAW_SPECIALIZATION] = (
            aggregatedRawData[VendorScore.RAW_TOTAL_SPEND] / aggregatedRawData["vendor_total_spend"].replace(0, np.nan)
        ).fillna(0.0)

        aggregatedRawData[VendorScore.RAW_AVERAGE_SAVING_PERCENT] = aggregatedRawData[VendorScore.RAW_AVERAGE_SAVING_PERCENT].fillna(0.0)

        # --- Scoreable subset -----------------------------------------
        valid_vendors                   = aggregatedRawData[aggregatedRawData[VendorScore.RAW_PURCHASE_COUNT] >= self.min_purchase_count].copy()
        vendors_with_insufficient_po    = aggregatedRawData[aggregatedRawData[VendorScore.RAW_PURCHASE_COUNT] < self.min_purchase_count].copy()

        rows: list[VendorScore] = []

        if not valid_vendors.empty:
           valid_vendors = self._add_normalized_columns(valid_vendors)
           valid_vendors = self._add_composite_score(valid_vendors)
           valid_vendors[VendorScore.PERFORMANCE_BAND] = valid_vendors.apply(
                lambda r: self._assign_performance_band(r[VendorScore.COMPOSITE_SCORE], r[VendorScore.RAW_PURCHASE_COUNT]), axis=1
            )
           
           for _, row in valid_vendors.iterrows():
                rows.append(VendorScore.from_series(run_id, row))

        # Insufficient data rows
        for _, row in vendors_with_insufficient_po.iterrows():
            rows.append(VendorScore.create_insufficient_data(run_id, row)) 

        logger.info(
            f"Scoring complete: {len(valid_vendors)} scored, "
            f"{len(vendors_with_insufficient_po)} insufficient_data pairs."
        )
        return rows
    
    def _add_normalized_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add normalized signal columns to *df* for debugging/inspection."""
        df = df.copy()
        df[VendorScore.SAVING_PERCENT_NORM]  = normalize(df[VendorScore.RAW_AVERAGE_SAVING_PERCENT])
        df[VendorScore.SPEND_NORM]           = normalize(df[VendorScore.RAW_TOTAL_SPEND])
        df[VendorScore.SPECIALIZATION_NORM]  = normalize(df[VendorScore.RAW_SPECIALIZATION])

        return df
    
    def _add_composite_score(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add composite score and performance band columns to *df* for debugging/inspection."""
        df = df.copy()
        df[VendorScore.COMPOSITE_SCORE] = (
            df[VendorScore.SAVING_PERCENT_NORM] * self.saving_weight
            + df[VendorScore.SPEND_NORM] * self.spend_weight
            + df[VendorScore.SPECIALIZATION_NORM] * self.specialization_weight
        ) * 100.0

        df[VendorScore.COMPOSITE_SCORE] = df[VendorScore.COMPOSITE_SCORE].round(2).clip(0, 100)
        return df
