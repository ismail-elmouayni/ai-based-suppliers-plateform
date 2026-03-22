"""Unit tests for VendorScorer."""

import pytest
import pandas as pd
import numpy as np
from vendor_scoring.scorer import VendorScorer, BAND_GREEN, BAND_AMBER, BAND_RED, BAND_INSUFFICIENT

BASE_CONFIG = {
    "vendor_scoring": {
        "saving_pct_weight": 0.50,
        "spend_weight": 0.30,
        "specialization_weight": 0.20,
        "min_po_count_for_scoring": 3,
        "band_green_min": 70,
        "band_amber_min": 40,
    }
}


def make_df(vendors_categories, saving_pct=0.15, spend=10000.0, n_po=5):
    """Build a synthetic scoring DataFrame."""
    rows = []
    po = 0
    for vendor, category in vendors_categories:
        for _ in range(n_po):
            rows.append({
                "CanonicalVendorName": vendor,
                "Category": category,
                "Saving_Pct": saving_pct,
                "Spend": spend,
                "PO_Number": f"PO-{po:04d}",
            })
            po += 1
    return pd.DataFrame(rows)


class TestVendorScorer:
    def setup_method(self):
        self.scorer = VendorScorer(BASE_CONFIG)

    def test_score_range(self):
        """All composite scores must be in [0, 100]."""
        df = make_df([("VENDOR A", "IT"), ("VENDOR B", "IT"), ("VENDOR C", "Logistics")])
        result = self.scorer.score(df, run_id=1)
        scored = result[result["PerformanceBand"] != BAND_INSUFFICIENT]
        assert (scored["CompositeScore"] >= 0).all()
        assert (scored["CompositeScore"] <= 100).all()

    def test_band_green(self):
        """Vendor with best metrics should receive GREEN band."""
        # Three vendors; one with top saving pct
        rows = []
        for v, sp, spend in [("BEST", 0.99, 500000), ("MID", 0.10, 50000), ("POOR", 0.01, 5000)]:
            for i in range(5):
                rows.append({"CanonicalVendorName": v, "Category": "IT", "Saving_Pct": sp, "Spend": spend, "PO_Number": f"PO-{v}-{i}"})
        df = pd.DataFrame(rows)
        result = self.scorer.score(df, run_id=1)
        best = result[result["CanonicalVendorName"] == "BEST"]["PerformanceBand"].iloc[0]
        assert best == BAND_GREEN

    def test_band_red(self):
        """Vendor with worst metrics should receive RED band."""
        rows = []
        for v, sp, spend in [("BEST", 0.99, 500000), ("MID", 0.10, 50000), ("POOR", 0.01, 5000)]:
            for i in range(5):
                rows.append({"CanonicalVendorName": v, "Category": "IT", "Saving_Pct": sp, "Spend": spend, "PO_Number": f"PO-{v}-{i}"})
        df = pd.DataFrame(rows)
        result = self.scorer.score(df, run_id=1)
        poor = result[result["CanonicalVendorName"] == "POOR"]["PerformanceBand"].iloc[0]
        assert poor == BAND_RED

    def test_insufficient_data_below_min_po(self):
        """Vendor-category pairs with < min_po_count should be INSUFFICIENT_DATA."""
        df = make_df([("VENDOR A", "IT")], n_po=2)  # 2 < 3
        result = self.scorer.score(df, run_id=1)
        assert (result["PerformanceBand"] == BAND_INSUFFICIENT).all()

    def test_weight_change_changes_score(self):
        """Changing weights should produce different composite scores."""
        df = make_df([("V1", "Cat1"), ("V2", "Cat1")], saving_pct=0.99, spend=1000.0)
        df2 = df.copy()
        df2.loc[df2["CanonicalVendorName"] == "V2", "Saving_Pct"] = 0.01
        df2.loc[df2["CanonicalVendorName"] == "V2", "Spend"] = 999999.0

        config_saving = dict(BASE_CONFIG)
        config_saving["vendor_scoring"] = dict(BASE_CONFIG["vendor_scoring"])
        config_saving["vendor_scoring"]["saving_pct_weight"] = 0.90
        config_saving["vendor_scoring"]["spend_weight"] = 0.05
        config_saving["vendor_scoring"]["specialization_weight"] = 0.05

        config_spend = dict(BASE_CONFIG)
        config_spend["vendor_scoring"] = dict(BASE_CONFIG["vendor_scoring"])
        config_spend["vendor_scoring"]["saving_pct_weight"] = 0.05
        config_spend["vendor_scoring"]["spend_weight"] = 0.90
        config_spend["vendor_scoring"]["specialization_weight"] = 0.05

        scorer_saving = VendorScorer(config_saving)
        scorer_spend = VendorScorer(config_spend)

        result_saving = scorer_saving.score(df2, run_id=1)
        result_spend = scorer_spend.score(df2, run_id=1)

        s1_saving = result_saving[result_saving["CanonicalVendorName"] == "V1"]["CompositeScore"].iloc[0]
        s1_spend = result_spend[result_spend["CanonicalVendorName"] == "V1"]["CompositeScore"].iloc[0]
        assert s1_saving != s1_spend

    def test_null_category_excluded(self):
        """Rows with NULL/None category are excluded before scoring."""
        rows = []
        for i in range(5):
            rows.append({"CanonicalVendorName": "V1", "Category": None, "Saving_Pct": 0.5, "Spend": 10000, "PO_Number": f"PO-{i}"})
        df = pd.DataFrame(rows)
        result = self.scorer.score(df, run_id=1)
        assert result.empty

    def test_specialization_sums_to_1_per_vendor(self):
        """RawSpecialization across all categories for one vendor sums to 1.0."""
        rows = []
        for cat, sp_ratio in [("IT", 0.6), ("Logistics", 0.4)]:
            for i in range(5):
                rows.append({
                    "CanonicalVendorName": "VENDOR A",
                    "Category": cat,
                    "Saving_Pct": 0.10,
                    "Spend": 60000.0 if cat == "IT" else 40000.0,
                    "PO_Number": f"PO-{cat}-{i}",
                })
        df = pd.DataFrame(rows)
        result = self.scorer.score(df, run_id=1)
        total_spec = result[result["CanonicalVendorName"] == "VENDOR A"]["RawSpecialization"].sum()
        assert abs(total_spec - 1.0) < 1e-6

    def test_output_columns(self):
        """Output DataFrame has all required columns."""
        df = make_df([("V1", "Cat1"), ("V2", "Cat1")])
        result = self.scorer.score(df, run_id=99)
        required = {"RunId", "CanonicalVendorName", "Category", "CompositeScore",
                    "PerformanceBand", "SavingPctNorm", "SpendNorm", "SpecializationNorm",
                    "RawSavingPct", "RawTotalSpend", "RawSpecialization", "POCount"}
        assert required.issubset(set(result.columns))
