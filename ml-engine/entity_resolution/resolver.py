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
from typing import Dict, List, Optional

import pandas as pd
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class VendorResolver:
    def __init__(self, config: dict):
        er_cfg = config.get("entity_resolution", {})
        self.match_threshold: float = er_cfg.get("match_threshold", 85)
        self.top_k_candidates: int = er_cfg.get("top_k_candidates", 5)
        self.normalize_before_match: bool = er_cfg.get("normalize_before_match", True)
        self.strip_suffixes: List[str] = [
            s.upper() for s in er_cfg.get("strip_suffixes", [])
        ]

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

    def _find(self, parent: Dict[str, str], x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(self, parent: Dict[str, str], x: str, y: str) -> None:
        rx, ry = self._find(parent, x), self._find(parent, y)
        if rx != ry:
            parent[ry] = rx

    def _cluster_names(
        self, unique_names: List[str], po_counts: Dict[str, int]
    ) -> Dict[str, str]:
        """
        Return {raw_name: canonical_name} mapping.

        Uses pairwise WRatio scoring and union-find clustering.
        Canonical = most-frequent name in cluster.
        """
        if not unique_names:
            return {}

        normalized = [self._normalize(n) for n in unique_names]
        parent = {n: n for n in unique_names}

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
        groups: Dict[str, List[str]] = defaultdict(list)
        for name in unique_names:
            root = self._find(parent, name)
            groups[root].append(name)

        # Canonical = highest PO-count member
        mapping: Dict[str, str] = {}
        for members in groups.values():
            canonical = max(members, key=lambda n: po_counts.get(n, 0))
            for m in members:
                mapping[m] = canonical

        return mapping

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(
        self, df: pd.DataFrame, run_id: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Resolve vendor names in *df* (must have 'Vendor' and 'PO_Number' columns).

        Returns a mapping DataFrame with columns:
            RawVendorName, CanonicalVendorName, MatchScore, MatchMethod,
            ResolutionRunId
        """
        if df.empty or "Vendor" not in df.columns:
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
        po_counts: Dict[str, int] = (
            df.groupby("Vendor")["PO_Number"].nunique().to_dict()
            if "PO_Number" in df.columns
            else {v: 1 for v in df["Vendor"].unique()}
        )

        unique_names = [str(n) for n in df["Vendor"].dropna().unique().tolist()]
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
