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
import re
from collections import defaultdict
from typing import Any

import pandas as pd
from rapidfuzz import fuzz, process

from config_types import EntityResolutionConfig
from data_source_columns import DataSourceColumns

logger = logging.getLogger(__name__)


class VendorResolver:
    def __init__(self, config: dict[str, Any]) -> None:
        cfg = EntityResolutionConfig.from_dict(config.get("entity_resolution", {}))
        self.match_threshold: float        = cfg.match_threshold
        self.top_k_candidates: int         = cfg.top_k_candidates
        self.normalize_before_match: bool  = cfg.normalize_before_match
        self.strip_suffixes: list[str]     = list(cfg.strip_suffixes)

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def _normalize(self, name: str) -> str:
        """Uppercase, collapse whitespace, optionally strip legal suffixes."""
        name = str(name).upper().strip()
        name = re.sub(r"\s+", " ", name)
        name = name.rstrip(",").strip()

        if self.strip_suffixes and self.normalize_before_match:
            # Strip trailing suffixes (with or without punctuation)
            for suffix in sorted(self.strip_suffixes, key=len, reverse=True):
                pattern = rf"\b{re.escape(suffix)}\.?\s*$"
                name = re.sub(pattern, "", name).strip().rstrip(",").strip()

        return name

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

    def _cluster_names(
        self, unique_names: list[str], po_counts: dict[str, int]
    ) -> dict[str, str]:
        """
        Return {raw_name: canonical_name} mapping.

        Uses pairwise WRatio scoring and union-find clustering.
        Canonical = most-frequent name in cluster.
        """
        if not unique_names:
            return {}

        normalized = [self._normalize(n) for n in unique_names]
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
        mapping: dict[str, str] = {}
        for members in groups.values():
            canonical = max(members, key=lambda n: po_counts.get(n, 0))
            for m in members:
                mapping[m] = canonical

        return mapping

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(
        self, df: pd.DataFrame, run_id: int | None = None
    ) -> pd.DataFrame:
        """
        Resolve vendor names in *df* (must have 'Vendor' and 'PO_Number' columns).

        Returns a mapping DataFrame with columns:
            RawVendorName, CanonicalVendorName, MatchScore, MatchMethod,
            ResolutionRunId
        """
        if df.empty or DataSourceColumns.VENDOR not in df.columns:
            logger.warning("resolve() called with empty or missing Vendor column.")
            return pd.DataFrame(
                columns=[
                    "RawVendorName",
                    "CanonicalVendorName",
                    "MatchScore",
                    "MatchMethod",
                    "ResolutionRunId",
                ]
            )

        # PO frequency per raw vendor name
        po_counts: dict[str, int] = (
            df.groupby(DataSourceColumns.VENDOR)[DataSourceColumns.PURCHASE_ORDERS_NUMBER].nunique().to_dict()
            if DataSourceColumns.PURCHASE_ORDERS_NUMBER in df.columns
            else {v: 1 for v in df[DataSourceColumns.VENDOR].unique()}
        )

        unique_names: list[str] = [str(n) for n in df[DataSourceColumns.VENDOR].dropna().unique().tolist()]
        logger.info(f"Resolving {len(unique_names)} unique vendor names...")

        mapping = self._cluster_names(unique_names, po_counts)

        rows = []
        for raw, canonical in mapping.items():
            norm_raw = self._normalize(raw)
            norm_can = self._normalize(canonical)
            score = (
                100.0
                if raw == canonical
                else fuzz.WRatio(norm_raw, norm_can)
            )
            method = "EXACT" if raw == canonical else "FUZZY_WRATIO"
            rows.append(
                {
                    "RawVendorName": raw,
                    "CanonicalVendorName": canonical,
                    "MatchScore": round(score, 2),
                    "MatchMethod": method,
                    "ResolutionRunId": run_id,
                }
            )

        result = pd.DataFrame(rows)
        logger.info(
            f"Resolution complete: {len(unique_names)} raw → "
            f"{result['CanonicalVendorName'].nunique()} canonical vendors."
        )
        return result
