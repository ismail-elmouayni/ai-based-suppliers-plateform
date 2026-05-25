"""Unit tests for VendorScorer."""

import pandas as pd
import numpy as np

from config_types import VendorScoringConfig
from data_source_columns import DataSourceColumns
from vendor_scoring.scorer import PerformanceBand, VendorScorer

BASE_CFG = VendorScoringConfig(
    saving_pct_weight=0.50,
    spend_weight=0.30,
    specialization_weight=0.20,
    min_purchase_count=3,
    band_green_min=70.0,
    band_amber_min=40.0,
)


def make_df(vendors_categories, saving_pct=0.15, spend=10000.0, n_po=5):
    """Build a synthetic scoring DataFrame."""
    rows = []
    po = 0
    for vendor, category in vendors_categories:
        for _ in range(n_po):
            rows.append({
                DataSourceColumns.CANONICAL_VENDOR: vendor,
                DataSourceColumns.CATEGORY: category,
                DataSourceColumns.SAVING_PERCENT: saving_pct,
                DataSourceColumns.SPEND: spend,
                DataSourceColumns.PURCHASE_ORDERS_NUMBER: f"PO-{po:04d}",
            })
            po += 1
    return pd.DataFrame(rows)


class TestVendorScorer:
    def setup_method(self):
        self.scorer = VendorScorer(BASE_CFG)

    def test_score_range(self):
        """All composite scores must be in [0, 100]."""
        df = make_df([("VENDOR A", "IT"), ("VENDOR B", "IT"), ("VENDOR C", "Logistics")])
        result = self.scorer.score(df, run_id=1)
        scored = result[result["PerformanceBand"] != PerformanceBand.INSUFFICIENT]
        assert (scored["CompositeScore"] >= 0).all()
        assert (scored["CompositeScore"] <= 100).all()

    def test_band_green(self):
        """Vendor with best metrics should receive GREEN band."""
        # Three vendors; one with top saving pct
        rows = []
        for v, sp, spend in [("BEST", 0.99, 500000), ("MID", 0.10, 50000), ("POOR", 0.01, 5000)]:
            for i in range(5):
                rows.append({DataSourceColumns.CANONICAL_VENDOR: v, DataSourceColumns.CATEGORY: "IT", DataSourceColumns.SAVING_PERCENT: sp, DataSourceColumns.SPEND: spend, DataSourceColumns.PURCHASE_ORDERS_NUMBER: f"PO-{v}-{i}"})
        df = pd.DataFrame(rows)
        result = self.scorer.score(df, run_id=1)
        best = result[result[DataSourceColumns.CANONICAL_VENDOR] == "BEST"]["PerformanceBand"].iloc[0]
        assert best == PerformanceBand.GREEN

    def test_band_red(self):
        """Vendor with worst metrics should receive RED band."""
        rows = []
        for v, sp, spend in [("BEST", 0.99, 500000), ("MID", 0.10, 50000), ("POOR", 0.01, 5000)]:
            for i in range(5):
                rows.append({DataSourceColumns.CANONICAL_VENDOR: v, DataSourceColumns.CATEGORY: "IT", DataSourceColumns.SAVING_PERCENT: sp, DataSourceColumns.SPEND: spend, DataSourceColumns.PURCHASE_ORDERS_NUMBER: f"PO-{v}-{i}"})
        df = pd.DataFrame(rows)
        result = self.scorer.score(df, run_id=1)
        poor = result[result[DataSourceColumns.CANONICAL_VENDOR] == "POOR"]["PerformanceBand"].iloc[0]
        assert poor == PerformanceBand.RED

    def test_insufficient_data_below_min_po(self):
        """Vendor-category pairs with < min_purchase_count should be INSUFFICIENT_DATA."""
        df = make_df([("VENDOR A", "IT")], n_po=2)  # 2 < 3
        result = self.scorer.score(df, run_id=1)
        assert (result["PerformanceBand"] == PerformanceBand.INSUFFICIENT).all()

    def test_weight_change_changes_score(self):
        """Changing weights should produce different composite scores."""
        df = make_df([("V1", "Cat1"), ("V2", "Cat1")], saving_pct=0.99, spend=1000.0)
        df2 = df.copy()
        df2.loc[df2[DataSourceColumns.CANONICAL_VENDOR] == "V2", DataSourceColumns.SAVING_PERCENT] = 0.01
        df2.loc[df2[DataSourceColumns.CANONICAL_VENDOR] == "V2", DataSourceColumns.SPEND] = 999999.0

        cfg_saving = VendorScoringConfig(saving_pct_weight=0.90, spend_weight=0.05, specialization_weight=0.05)
        cfg_spend  = VendorScoringConfig(saving_pct_weight=0.05, spend_weight=0.90, specialization_weight=0.05)

        scorer_saving = VendorScorer(cfg_saving)
        scorer_spend  = VendorScorer(cfg_spend)

        result_saving = scorer_saving.score(df2, run_id=1)
        result_spend = scorer_spend.score(df2, run_id=1)

        s1_saving = result_saving[result_saving[DataSourceColumns.CANONICAL_VENDOR] == "V1"]["CompositeScore"].iloc[0]
        s1_spend = result_spend[result_spend[DataSourceColumns.CANONICAL_VENDOR] == "V1"]["CompositeScore"].iloc[0]
        assert s1_saving != s1_spend

    def test_null_category_excluded(self):
        """Rows with NULL/None category are excluded before scoring."""
        rows = []
        for i in range(5):
            rows.append({DataSourceColumns.CANONICAL_VENDOR: "V1", DataSourceColumns.CATEGORY: None, DataSourceColumns.SAVING_PERCENT: 0.5, DataSourceColumns.SPEND: 10000, DataSourceColumns.PURCHASE_ORDERS_NUMBER: f"PO-{i}"})
        df = pd.DataFrame(rows)
        result = self.scorer.score(df, run_id=1)
        assert result.empty

    def test_specialization_sums_to_1_per_vendor(self):
        """RawSpecialization across all categories for one vendor sums to 1.0."""
        rows = []
        for cat, sp_ratio in [("IT", 0.6), ("Logistics", 0.4)]:
            for i in range(5):
                rows.append({
                    DataSourceColumns.CANONICAL_VENDOR: "VENDOR A",
                    DataSourceColumns.CATEGORY: cat,
                    DataSourceColumns.SAVING_PERCENT: 0.10,
                    DataSourceColumns.SPEND: 60000.0 if cat == "IT" else 40000.0,
                    DataSourceColumns.PURCHASE_ORDERS_NUMBER: f"PO-{cat}-{i}",
                })
        df = pd.DataFrame(rows)
        result = self.scorer.score(df, run_id=1)
        total_spec = result[result[DataSourceColumns.CANONICAL_VENDOR] == "VENDOR A"]["RawSpecialization"].sum()
        assert abs(total_spec - 1.0) < 1e-6

    def test_output_columns(self):
        """Output DataFrame has all required columns."""
        df = make_df([("V1", "Cat1"), ("V2", "Cat1")])
        result = self.scorer.score(df, run_id=99)
        required = {"RunId", DataSourceColumns.CANONICAL_VENDOR, DataSourceColumns.CATEGORY, "CompositeScore",
                    "PerformanceBand", "SavingPctNorm", "SpendNorm", "SpecializationNorm",
                    "RawSavingPct", "RawTotalSpend", "RawSpecialization", "PurchaseCount"}
        assert required.issubset(set(result.columns))
