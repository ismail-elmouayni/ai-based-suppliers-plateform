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
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler

from config_types import ConsolidationConfig
from data_source_columns import DataSourceColumns

logger = logging.getLogger(__name__)


class VendorClusterer:
    def __init__(self, config: dict[str, Any]) -> None:
        cfg = ConsolidationConfig.from_dict(config.get("consolidation", {}))
        self.min_cluster_size: int   = cfg.min_cluster_size
        self.algorithm: str          = cfg.algorithm
        self.n_clusters              = cfg.n_clusters
        self.dbscan_eps: float       = cfg.dbscan_eps
        self.dbscan_min_samples: int = cfg.dbscan_min_samples

    # ------------------------------------------------------------------
    # Elbow method
    # ------------------------------------------------------------------

    def _auto_k(self, X: np.ndarray) -> int:
        """Pick k using the elbow method (inertia reduction < 15%)."""
        max_k = min(10, len(X) - 1)
        if max_k < 2:
            return max(1, len(X))

        inertias = []
        ks = list(range(2, max_k + 1))
        for k in ks:
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            km.fit(X)
            inertias.append(km.inertia_)

        # Pick first k where reduction from previous < 15%
        for i in range(1, len(inertias)):
            reduction = (inertias[i - 1] - inertias[i]) / (inertias[i - 1] + 1e-9)
            if reduction < 0.15:
                return ks[i - 1]

        # Fallback: min(8, n_vendors // 5)
        return min(8, max(2, len(X) // 5))

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

    def cluster(self, df: pd.DataFrame, run_id: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Cluster vendors by spend pattern.

        Required columns: CanonicalVendorName, Category, Spend, Saving_Pct.
        Returns (clusters_df, members_df) ready for DataRepository.write_consolidation().
        """
        if df.empty:
            logger.warning("cluster() called with empty DataFrame.")
            return pd.DataFrame(), pd.DataFrame()

        # Filter NULL categories
        df = df[df[DataSourceColumns.CATEGORY].notna()].copy()
        null_sentinels = {"NULL", "None", "nan", ""}
        df = df[~df[DataSourceColumns.CATEGORY].astype(str).isin(null_sentinels)].copy()

        if df.empty or df[DataSourceColumns.CANONICAL_VENDOR].nunique() < 2:
            logger.warning("Not enough vendors to cluster after filtering.")
            return pd.DataFrame(), pd.DataFrame()

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

        cluster_rows = []
        member_rows = []

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
                {
                    "RunId": run_id,
                    "ClusterLabel": int(label),
                    "DominantCategory": dominant_cat,
                    "VendorCount": len(cluster_vendors),
                    "TotalSpendAtStake": total_spend,
                    "EstimatedSavingPct": round(est_saving_pct, 6),
                    "EstimatedSavingAmount": round(est_saving_amount, 2),
                }
            )

            for v in cluster_vendors:
                member_rows.append(
                    {
                        "ClusterLabel": int(label),
                        "CanonicalVendorName": v,
                        "VendorTotalSpend": float(vendor_total_spend.get(v, 0)),
                        "CategoriesSupplied": str(vendor_categories.get(v, "")),
                    }
                )

        clusters_df = pd.DataFrame(cluster_rows)
        members_df = pd.DataFrame(member_rows)

        logger.info(
            f"Clustering complete: {len(clusters_df)} clusters with ≥ "
            f"{self.min_cluster_size} vendors."
        )
        return clusters_df, members_df
