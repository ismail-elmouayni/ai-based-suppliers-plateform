"""
VendorClusterer — vendor consolidation opportunity detection via KMeans clustering.

Steps:
1. Build vendor × category spend matrix (fill NaN → 0)
2. StandardScaler normalise
3. Auto-k elbow: try k=2..10, pick first k where inertia reduction < 15%
4. KMeans(n_clusters=k, random_state=42, n_init=10)
5. For each cluster with ≥ min_cluster_size vendors:
   - DominantCategory = argmax mean spend per category
   - EstimatedSavingPct = best vendor saving_pct − mean saving_pct in DominantCategory
   - EstimatedSavingAmount = TotalSpendAtStake × EstimatedSavingPct
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler

from config_types import ConsolidationConfig
from consolidation.cluster_result import ClusterMember, ClusteringResult, ConsolidationCluster
from core.raw_data_processing import RawDataProcessing
from data_source_columns import DataSourceColumns

logger = logging.getLogger(__name__)

# the minimal number of cluster to make kMeans method useful.
kmean_min_cluster_size: int = 10

class VendorClusterer:
    def __init__(self, cfg: ConsolidationConfig) -> None:
        self.min_cluster_size: int   = cfg.min_cluster_size
        self.algorithm: str          = cfg.algorithm
        self.n_clusters              = cfg.n_clusters
        self.dbscan_eps: float       = cfg.dbscan_eps
        self.dbscan_min_samples: int = cfg.dbscan_min_samples

    # ------------------------------------------------------------------
    # Elbow method
    # ------------------------------------------------------------------

    def _auto_k(self, scaled_matrix: np.ndarray) -> int:
        """Pick k using the elbow method (inertia reduction < 15%)."""

        max_clusters = min(kmean_min_cluster_size, len(scaled_matrix) - 1)
        if max_clusters < 2:
            return max(1, len(scaled_matrix))

        inertia_per_k = []
        candidate_k_values = list(range(2, max_clusters + 1))

        for n_clusters in candidate_k_values:
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            kmeans.fit(scaled_matrix)
            inertia_per_k.append(kmeans.inertia_)

        # Pick first k where inertia reduction from the previous k is < 15% (elbow point)
        for k_index in range(1, len(inertia_per_k)):
            inertia_reduction_ratio = (
                (inertia_per_k[k_index - 1] - inertia_per_k[k_index])
                / (inertia_per_k[k_index - 1] + 1e-9)
            )
            if inertia_reduction_ratio < 0.15:
                return candidate_k_values[k_index - 1]

        # Fallback: min(8, n_vendors // 5)
        return min(8, max(2, len(scaled_matrix) // 5))

    # ------------------------------------------------------------------
    # Clustering
    # ------------------------------------------------------------------

    def _cluster_kmeans(self, X_scaled: np.ndarray, n_clusters: int) -> np.ndarray:
        km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        return km.fit_predict(X_scaled)

    def _cluster_dbscan(self, X_scaled: np.ndarray) -> np.ndarray:
        db = DBSCAN(eps=self.dbscan_eps, min_samples=self.dbscan_min_samples)
        return db.fit_predict(X_scaled)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def cluster(self, df: pd.DataFrame, run_id: int) -> ClusteringResult:
        """
        Cluster vendors by spend pattern.

        Required columns: CanonicalVendorName, Category, Spend, Saving_Pct.
        Returns (clusters, members) as typed domain object lists.
        """
        if df.empty:
            logger.warning("cluster() called with empty DataFrame.")
            return ClusteringResult(clusters=[], members=[])

        # Filter NULL categories
        df = RawDataProcessing.drop_null_column(df, DataSourceColumns.CATEGORY)

        if df.empty or df[DataSourceColumns.CANONICAL_VENDOR].nunique() < 2:
            logger.warning("Not enough vendors to cluster after filtering.")
            return ClusteringResult(clusters=[], members=[])

        # Vendor × category spend pivot
        pivot = (
            df.groupby([DataSourceColumns.CANONICAL_VENDOR, DataSourceColumns.CATEGORY])[DataSourceColumns.SPEND]
            .sum()
            .unstack(fill_value=0.0)
        )
        vendors = pivot.index.tolist()
        categories = pivot.columns.tolist()
        X = pivot.values.astype(float)

        # Scale
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Cluster
        if self.algorithm == "dbscan":
            labels = self._cluster_dbscan(X_scaled)
        else:
            n_k = (
                self._auto_k(X_scaled)
                if str(self.n_clusters).lower() == "auto"
                else int(self.n_clusters)
            )
            n_k = min(n_k, len(vendors))
            labels = self._cluster_kmeans(X_scaled, n_k)

        # Vendor-level info
        vendor_total_spend = (
            df.groupby(DataSourceColumns.CANONICAL_VENDOR)[DataSourceColumns.SPEND].sum().reindex(vendors).fillna(0)
        )
        vendor_saving_pct = (
            df.groupby(DataSourceColumns.CANONICAL_VENDOR)[DataSourceColumns.SAVING_PERCENT].mean().reindex(vendors).fillna(0)
        )
        vendor_categories = (
            df.groupby(DataSourceColumns.CANONICAL_VENDOR)[DataSourceColumns.CATEGORY]
            .apply(lambda x: ", ".join(sorted(x.unique())))
            .reindex(vendors)
            .fillna("")
        )

        cluster_rows: list[ConsolidationCluster] = []
        member_rows: list[ClusterMember] = []

        for label in set(labels):
            if label == -1:  # DBSCAN noise
                continue

            mask = labels == label
            cluster_vendors = [v for v, m in zip(vendors, mask) if m]

            if len(cluster_vendors) < self.min_cluster_size:
                continue

            # Cluster spend profile
            cluster_X = X[mask]  # shape: (n_vendors, n_categories)
            mean_spend_per_cat = cluster_X.mean(axis=0)
            dominant_cat_idx = int(np.argmax(mean_spend_per_cat))
            dominant_cat = categories[dominant_cat_idx]

            total_spend = float(vendor_total_spend[cluster_vendors].sum())

            # Saving estimate: best vendor's saving pct − mean in cluster on dominant category
            cluster_saving_pcts = [
                float(vendor_saving_pct.get(v, 0)) for v in cluster_vendors
            ]
            best_saving_pct = max(cluster_saving_pcts) if cluster_saving_pcts else 0.0
            mean_saving_pct = np.mean(cluster_saving_pcts) if cluster_saving_pcts else 0.0
            est_saving_pct = max(0.0, float(best_saving_pct - mean_saving_pct))
            est_saving_amount = total_spend * est_saving_pct

            cluster_rows.append(
                ConsolidationCluster(
                    run_id=run_id,
                    cluster_label=int(label),
                    dominant_category=dominant_cat,
                    vendor_count=len(cluster_vendors),
                    total_spend_at_stake=total_spend,
                    estimated_saving_pct=round(est_saving_pct, 6),
                    estimated_saving_amount=round(est_saving_amount, 2),
                )
            )

            for v in cluster_vendors:
                member_rows.append(
                    ClusterMember(
                        cluster_label=int(label),
                        canonical_vendor_name=v,
                        vendor_total_spend=float(vendor_total_spend.get(v, 0)),
                        categories_supplied=str(vendor_categories.get(v, "")),
                    )
                )

        logger.info(
            f"Clustering complete: {len(cluster_rows)} clusters with ≥ "
            f"{self.min_cluster_size} vendors."
        )
        return ClusteringResult(clusters=cluster_rows, members=member_rows)
