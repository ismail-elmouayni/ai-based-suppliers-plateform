"""
VendorResolver — fuzzy entity resolution for vendor names.

Algorithm:
1. Normalise all raw names (uppercase, strip whitespace, optionally strip legal suffixes)
2. Compute pairwise WRatio scores via rapidfuzz.process.cdist
3. Group names into clusters where any pair scores ≥ match_threshold
4. Canonical name = name with the highest PO frequency in each cluster
5. Write mapping to procurement.ResolvedVendors
"""

from __future__ import annotations

import logging
from collections import defaultdict, namedtuple

import pandas as pd
from rapidfuzz import fuzz, process

from config_types import EntityResolutionConfig
from core.string_processing import StringProcessing
from data_source_columns import DataSourceColumns
from entity_resolution.vendor_mapping import VendorMapping

logger = logging.getLogger(__name__)

_NameMapping = namedtuple("_NameMapping", ["raw_name", "canonical_name"])


class VendorResolver:
    def __init__(self, cfg: EntityResolutionConfig) -> None:
        self.match_threshold: float        = cfg.match_threshold
        self.top_k_candidates: int         = cfg.top_k_candidates
        self.normalize_before_match: bool  = cfg.normalize_before_match
        self.strip_suffixes: list[str]     = list(cfg.strip_suffixes)

    # ------------------------------------------------------------------
    # Clustering via union-find
    # ------------------------------------------------------------------

    def _find(self, parent: dict[str, str], x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(self, parent: dict[str, str], x: str, y: str) -> None:
        rx, ry = self._find(parent, x), self._find(parent, y)
        if rx != ry:
            parent[ry] = rx

    def _cluster_names(self, unique_names: list[str], po_counts: dict[str, int]) -> list[_NameMapping]:
        """
        Return {raw_name: canonical_name} mapping.

        Uses pairwise WRatio scoring and union-find clustering.
        Canonical = most-frequent name in cluster.
        """
        if not unique_names:
            return []

        normalized = [
            StringProcessing.normalize(n, strip_suffixes=self.strip_suffixes, normalize_before_match=self.normalize_before_match)
            for n in unique_names
        ]
        parent: dict[str, str] = {n: n for n in unique_names}

        # Build pairwise score matrix via cdist (more efficient than nested loops)
        from rapidfuzz.process import cdist as rfd_cdist

        scores = rfd_cdist(
            normalized,
            normalized,
            scorer=fuzz.WRatio,
            score_cutoff=self.match_threshold,
            workers=1,
        )

        n = len(unique_names)
        for i in range(n):
            for j in range(i + 1, n):
                if scores[i][j] >= self.match_threshold:
                    self._union(parent, unique_names[i], unique_names[j])

        # Group by root
        groups: dict[str, list[str]] = defaultdict(list)
        for name in unique_names:
            root = self._find(parent, name)
            groups[root].append(name)

        # Canonical = highest PO-count member
        mappings: list[_NameMapping] = []
        for members in groups.values():
            canonical = max(members, key=lambda n: po_counts.get(n, 0))
            for m in members:
                mappings.append(_NameMapping(raw_name=m, canonical_name=canonical))

        return mappings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, df: pd.DataFrame, run_id: int | None = None ) -> list[VendorMapping]:
        """
        Resolve vendor names in *df* (must have 'Vendor' and 'PO_Number' columns).

        Returns a list of VendorMapping objects (one per unique raw vendor name).
        """
        if df.empty or DataSourceColumns.VENDOR not in df.columns:
            logger.warning("resolve() called with empty or missing Vendor column.")
            return []

        # PO frequency per raw vendor name
        po_counts: dict[str, int] = (
            df.groupby(DataSourceColumns.VENDOR)[DataSourceColumns.PURCHASE_ORDERS_NUMBER].nunique().to_dict()
            if DataSourceColumns.PURCHASE_ORDERS_NUMBER in df.columns
            else {v: 1 for v in df[DataSourceColumns.VENDOR].unique()}
        )

        unique_names: list[str] = [str(n) for n in df[DataSourceColumns.VENDOR].dropna().unique().tolist()]
        logger.info(f"Resolving {len(unique_names)} unique vendor names...")

        mapping = self._cluster_names(unique_names, po_counts)

        mappings: list[VendorMapping] = []
        for entry in mapping:
            norm_raw = StringProcessing.normalize(entry.raw_name, strip_suffixes=self.strip_suffixes, normalize_before_match=self.normalize_before_match)
            norm_can = StringProcessing.normalize(entry.canonical_name, strip_suffixes=self.strip_suffixes, normalize_before_match=self.normalize_before_match)
            score = (
                100.0
                if entry.raw_name == entry.canonical_name
                else fuzz.WRatio(norm_raw, norm_can)
            )
            method = "EXACT" if entry.raw_name == entry.canonical_name else "FUZZY_WRATIO"
            mappings.append(
                VendorMapping(
                    raw_vendor_name=entry.raw_name,
                    canonical_vendor_name=entry.canonical_name,
                    match_score=round(score, 2),
                    match_method=method,
                    resolution_run_id=run_id,
                )
            )

        unique_canonical = len({m.canonical_vendor_name for m in mappings})
        logger.info(
            f"Resolution complete: {len(unique_names)} raw → "
            f"{unique_canonical} canonical vendors."
        )
        return mappings
