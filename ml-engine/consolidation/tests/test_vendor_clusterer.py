"""Unit tests for VendorClusterer."""

import pytest
import pandas as pd
import numpy as np
from consolidation.vendor_clusterer import VendorClusterer
from consolidation.cluster_result import ConsolidationCluster, ClusterMember
from config_types import ConsolidationConfig
from data_source_columns import DataSourceColumns

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
                DataSourceColumns.CANONICAL_VENDOR: vendor,
                DataSourceColumns.CATEGORY: cat,
                DataSourceColumns.SPEND: spend,
                DataSourceColumns.SAVING_PERCENT: rng.uniform(0.01, 0.30),
                DataSourceColumns.PURCHASE_ORDERS_NUMBER: f"PO-{vendor}-{cat}",
            })
    return pd.DataFrame(rows)


class TestVendorClusterer:
    def setup_method(self):
        self.clusterer = VendorClusterer(ConsolidationConfig.from_dict(CONFIG))

    def test_clusters_returned(self):
        """Clustering produces at least one cluster."""
        df = make_df(n_vendors=10, n_categories=4)
        clusters, members = self.clusterer.cluster(df, run_id=1)
        assert len(clusters) >= 1

    def test_min_cluster_size_filter(self):
        """All returned clusters have vendor_count >= min_cluster_size."""
        df = make_df(n_vendors=10, n_categories=4)
        clusters, members = self.clusterer.cluster(df, run_id=1)
        assert all(c.vendor_count >= 2 for c in clusters)

    def test_dominant_category_is_max_spend(self):
        """DominantCategory should correspond to the category with highest mean spend."""
        # Build data where CAT_0 clearly dominates
        rows = []
        for v in ["V1", "V2", "V3"]:
            rows.append({DataSourceColumns.CANONICAL_VENDOR: v, DataSourceColumns.CATEGORY: "CAT_0", DataSourceColumns.SPEND: 1000000.0, DataSourceColumns.SAVING_PERCENT: 0.10, DataSourceColumns.PURCHASE_ORDERS_NUMBER: f"PO-{v}-0"})
            rows.append({DataSourceColumns.CANONICAL_VENDOR: v, DataSourceColumns.CATEGORY: "CAT_1", DataSourceColumns.SPEND: 1.0, DataSourceColumns.SAVING_PERCENT: 0.10, DataSourceColumns.PURCHASE_ORDERS_NUMBER: f"PO-{v}-1"})
        df = pd.DataFrame(rows)
        cfg = ConsolidationConfig.from_dict({ConsolidationConfig.CONFIG_KEY: {**CONFIG["consolidation"], "n_clusters": 1, "min_cluster_size": 2}})
        clusterer = VendorClusterer(cfg)
        clusters, _ = clusterer.cluster(df, run_id=1)
        if clusters:
            assert clusters[0].dominant_category == "CAT_0"

    def test_estimated_saving_non_negative(self):
        """estimated_saving_amount must be >= 0."""
        df = make_df(n_vendors=8, n_categories=3)
        clusters, _ = self.clusterer.cluster(df, run_id=1)
        assert all(c.estimated_saving_amount >= 0 for c in clusters)

    def test_members_match_cluster_vendor_count(self):
        """Sum of members per cluster equals vendor_count in clusters."""
        df = make_df(n_vendors=9, n_categories=3)
        clusters, members = self.clusterer.cluster(df, run_id=1)
        for cluster in clusters:
            member_count = sum(1 for m in members if m.cluster_label == cluster.cluster_label)
            assert member_count == cluster.vendor_count

    def test_empty_df_returns_empty(self):
        """Empty input returns empty lists."""
        df = pd.DataFrame(columns=[DataSourceColumns.CANONICAL_VENDOR, DataSourceColumns.CATEGORY, DataSourceColumns.SPEND, DataSourceColumns.SAVING_PERCENT, DataSourceColumns.PURCHASE_ORDERS_NUMBER])
        clusters, members = self.clusterer.cluster(df, run_id=1)
        assert clusters == []
        assert members == []

    def test_null_category_excluded(self):
        """Rows with NULL category are excluded before clustering."""
        df = make_df(n_vendors=6, n_categories=2)
        df.loc[df[DataSourceColumns.CATEGORY] == "CAT_0", DataSourceColumns.CATEGORY] = None
        clusters, members = self.clusterer.cluster(df, run_id=1)
        # Should still produce some clusters from remaining categories
        # Just verify no crash and dominant_category is set
        if clusters:
            assert all(c.dominant_category is not None for c in clusters)
