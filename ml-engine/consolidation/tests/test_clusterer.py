"""Unit tests for VendorClusterer."""

import pytest
import pandas as pd
import numpy as np
from consolidation.clusterer import VendorClusterer

CONFIG = {
    "consolidation": {
        "min_cluster_size": 2,
        "algorithm": "kmeans",
        "n_clusters": 3,
        "dbscan_eps": 0.5,
        "dbscan_min_samples": 2,
    }
}


def make_df(n_vendors=6, n_categories=3, seed=42):
    """Build a synthetic spend DataFrame."""
    rng = np.random.RandomState(seed)
    rows = []
    vendors = [f"VENDOR_{i}" for i in range(n_vendors)]
    categories = [f"CAT_{j}" for j in range(n_categories)]
    for vendor in vendors:
        for cat in categories:
            spend = rng.uniform(1000, 100000)
            rows.append({
                "CanonicalVendorName": vendor,
                "Category": cat,
                "Spend": spend,
                "Saving_Pct": rng.uniform(0.01, 0.30),
                "PO_Number": f"PO-{vendor}-{cat}",
            })
    return pd.DataFrame(rows)


class TestVendorClusterer:
    def setup_method(self):
        self.clusterer = VendorClusterer(CONFIG)

    def test_clusters_returned(self):
        """Clustering produces at least one cluster."""
        df = make_df(n_vendors=10, n_categories=4)
        clusters, members = self.clusterer.cluster(df, run_id=1)
        assert len(clusters) >= 1

    def test_min_cluster_size_filter(self):
        """All returned clusters have VendorCount >= min_cluster_size."""
        df = make_df(n_vendors=10, n_categories=4)
        clusters, members = self.clusterer.cluster(df, run_id=1)
        assert (clusters["VendorCount"] >= 2).all()

    def test_dominant_category_is_max_spend(self):
        """DominantCategory should correspond to the category with highest mean spend."""
        # Build data where CAT_0 clearly dominates
        rows = []
        for v in ["V1", "V2", "V3"]:
            rows.append({"CanonicalVendorName": v, "Category": "CAT_0", "Spend": 1000000.0, "Saving_Pct": 0.10, "PO_Number": f"PO-{v}-0"})
            rows.append({"CanonicalVendorName": v, "Category": "CAT_1", "Spend": 1.0, "Saving_Pct": 0.10, "PO_Number": f"PO-{v}-1"})
        df = pd.DataFrame(rows)
        config = dict(CONFIG)
        config["consolidation"] = dict(CONFIG["consolidation"])
        config["consolidation"]["n_clusters"] = 1
        config["consolidation"]["min_cluster_size"] = 2
        clusterer = VendorClusterer(config)
        clusters, _ = clusterer.cluster(df, run_id=1)
        if not clusters.empty:
            assert clusters.iloc[0]["DominantCategory"] == "CAT_0"

    def test_estimated_saving_non_negative(self):
        """EstimatedSavingAmount must be ≥ 0."""
        df = make_df(n_vendors=8, n_categories=3)
        clusters, _ = self.clusterer.cluster(df, run_id=1)
        assert (clusters["EstimatedSavingAmount"] >= 0).all()

    def test_members_match_cluster_vendor_count(self):
        """Sum of members per cluster equals VendorCount in clusters_df."""
        df = make_df(n_vendors=9, n_categories=3)
        clusters, members = self.clusterer.cluster(df, run_id=1)
        for _, row in clusters.iterrows():
            label = row["ClusterLabel"]
            member_count = len(members[members["ClusterLabel"] == label])
            assert member_count == row["VendorCount"]

    def test_empty_df_returns_empty(self):
        """Empty input returns empty DataFrames."""
        df = pd.DataFrame(columns=["CanonicalVendorName", "Category", "Spend", "Saving_Pct", "PO_Number"])
        clusters, members = self.clusterer.cluster(df, run_id=1)
        assert clusters.empty
        assert members.empty

    def test_null_category_excluded(self):
        """Rows with NULL category are excluded before clustering."""
        df = make_df(n_vendors=6, n_categories=2)
        df.loc[df["Category"] == "CAT_0", "Category"] = None
        clusters, members = self.clusterer.cluster(df, run_id=1)
        # Should still produce some clusters from remaining categories
        # Just verify no crash and NoneType not in DominantCategory
        if not clusters.empty:
            assert clusters["DominantCategory"].notna().all()
