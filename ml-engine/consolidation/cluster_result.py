"""
Domain types for consolidation clustering results.

ConsolidationCluster — summary row per cluster.
ClusterMember        — one vendor belonging to a cluster.
ClusteringResult     — wrapper returned by VendorClusterer.cluster().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple


@dataclass
class ConsolidationCluster:
    RUN_ID                 = "run_id"
    CLUSTER_LABEL          = "cluster_label"
    DOMINANT_CATEGORY      = "dominant_category"
    VENDOR_COUNT           = "vendor_count"
    TOTAL_SPEND_AT_STAKE   = "total_spend_at_stake"
    ESTIMATED_SAVING_PCT   = "estimated_saving_pct"
    ESTIMATED_SAVING_AMOUNT = "estimated_saving_amount"

    run_id: int
    cluster_label: int
    dominant_category: str
    vendor_count: int
    total_spend_at_stake: float
    estimated_saving_pct: float
    estimated_saving_amount: float


@dataclass
class ClusterMember:
    CLUSTER_LABEL         = "cluster_label"
    CANONICAL_VENDOR_NAME = "canonical_vendor_name"
    VENDOR_TOTAL_SPEND    = "vendor_total_spend"
    CATEGORIES_SUPPLIED   = "categories_supplied"

    cluster_label: int
    canonical_vendor_name: str
    vendor_total_spend: float
    categories_supplied: str


class ClusteringResult(NamedTuple):
    """Return value of VendorClusterer.cluster()."""
    clusters: list[ConsolidationCluster]
    members:  list[ClusterMember]
