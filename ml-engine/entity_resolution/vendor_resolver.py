"""
VendorResolver — fuzzy entity resolution for vendor names.

Algorithm:
1. Normalise all raw names (uppercase, strip whitespace, optionally strip legal suffixes)
2. Expand known token aliases (e.g. "TP" → "TELEPERFORMANCE")
3. Phase-0 VAT unions: vendors sharing the same non-null VAT are force-merged
4. Compute pairwise WRatio scores via rapidfuzz.process.cdist
   - Pairs with different non-null VATs are skipped (hard block)
5. Group names into clusters where any pair scores ≥ match_threshold
6. Canonical name = name with the highest PO frequency in each cluster
7. Write mapping to procurement.ResolvedVendors
"""

from __future__ import annotations

import logging
from collections import defaultdict, namedtuple

import pandas as pd
from rapidfuzz import fuzz

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
        self.token_aliases: dict[str, str] = cfg.token_aliases_dict()

    # ------------------------------------------------------------------
    # Union-find helpers
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

    # ------------------------------------------------------------------
    # Name clustering
    # ------------------------------------------------------------------

    def _cluster_names(
        self,
        unique_names: list[str],
        po_counts: dict[str, int],
        vendor_vat: dict[str, str | None],
    ) -> list[_NameMapping]:
        """Return _NameMapping(raw_name, canonical_name) for every unique vendor.

        Steps:
        1. Normalise → expand aliases → build parent dict
        2. Phase-0 VAT force-unions (same non-null VAT → same cluster)
        3. WRatio cdist, skipping pairs with conflicting VATs
        4. Group by root; canonical = highest PO-count member
        """
        if not unique_names:
            return []

        # Step 1: normalise then expand known aliases
        normalized = [
            StringProcessing.expand_token_aliases(
                StringProcessing.normalize(
                    n,
                    strip_suffixes=self.strip_suffixes,
                    normalize_before_match=self.normalize_before_match,
                ),
                self.token_aliases,
            )
            for n in unique_names
        ]

        parent: dict[str, str] = {n: n for n in unique_names}

        # Step 2: Phase-0 VAT force-unions
        n = len(unique_names)
        for i in range(n):
            vat_i = vendor_vat.get(unique_names[i])
            if not vat_i:
                continue
            for j in range(i + 1, n):
                vat_j = vendor_vat.get(unique_names[j])
                if vat_j and vat_i == vat_j:
                    self._union(parent, unique_names[i], unique_names[j])

        # Step 3: WRatio pairwise scoring (block on VAT mismatch)
        from rapidfuzz.process import cdist as rfd_cdist

        scores = rfd_cdist(
            normalized,
            normalized,
            scorer=fuzz.WRatio,
            score_cutoff=self.match_threshold,
            workers=1,
        )

        for i in range(n):
            vat_i = vendor_vat.get(unique_names[i])
            for j in range(i + 1, n):
                if scores[i][j] < self.match_threshold:
                    continue
                vat_j = vendor_vat.get(unique_names[j])
                # Hard block: both have non-null but different VATs
                if vat_i and vat_j and vat_i != vat_j:
                    continue
                self._union(parent, unique_names[i], unique_names[j])

        # Step 4: group by root; canonical = highest PO-count member
        groups: dict[str, list[str]] = defaultdict(list)
        for name in unique_names:
            groups[self._find(parent, name)].append(name)

        mappings: list[_NameMapping] = []
        for members in groups.values():
            canonical = max(members, key=lambda nm: po_counts.get(nm, 0))
            for m in members:
                mappings.append(_NameMapping(raw_name=m, canonical_name=canonical))

        return mappings

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(self, df: pd.DataFrame, run_id: int | None = None) -> list[VendorMapping]:
        """Resolve vendor names in *df*.

        *df* must contain a ``Vendor`` column.  ``PO_Number`` and ``VATNumber``
        columns are used when present but are not required.

        Returns one :class:`VendorMapping` per unique raw vendor name.
        """
        if df.empty or DataSourceColumns.VENDOR not in df.columns:
            logger.warning("resolve() called with empty or missing Vendor column.")
            return []

        # PO frequency per raw vendor name
        po_counts: dict[str, int] = (
            df.groupby(DataSourceColumns.VENDOR)[DataSourceColumns.PURCHASE_ORDERS_NUMBER]
            .nunique().to_dict()
            if DataSourceColumns.PURCHASE_ORDERS_NUMBER in df.columns
            else {v: 1 for v in df[DataSourceColumns.VENDOR].unique()}
        )

        # VAT per raw vendor name (mode of non-null values; None when unavailable)
        vendor_vat: dict[str, str | None] = {}
        if DataSourceColumns.VAT_NUMBER in df.columns:
            vendor_vat = (
                df.groupby(DataSourceColumns.VENDOR)[DataSourceColumns.VAT_NUMBER]
                .agg(lambda s: s.dropna().mode().iloc[0] if s.notna().any() else None)
                .to_dict()
            )

        unique_names: list[str] = [
            str(n) for n in df[DataSourceColumns.VENDOR].dropna().unique().tolist()
        ]
        logger.info("Resolving %d unique vendor names...", len(unique_names))

        mapping = self._cluster_names(unique_names, po_counts, vendor_vat)

        # Canonical VAT: VAT of the canonical vendor name
        canonical_vat: dict[str, str | None] = {
            m.canonical_name: vendor_vat.get(m.canonical_name) for m in mapping
        }

        mappings: list[VendorMapping] = []
        for entry in mapping:
            if entry.raw_name == entry.canonical_name:
                score = 100.0
                method = "EXACT"
            else:
                # Determine method from actual cause of the merge
                vat_raw = vendor_vat.get(entry.raw_name)
                vat_can = vendor_vat.get(entry.canonical_name)
                if vat_raw and vat_can and vat_raw == vat_can:
                    # Phase-0 VAT force-merge
                    score = 100.0
                    method = "VAT_FORCE_MERGE"
                else:
                    # Score on alias-expanded names (same representation used during clustering)
                    exp_raw = StringProcessing.expand_token_aliases(
                        StringProcessing.normalize(
                            entry.raw_name,
                            strip_suffixes=self.strip_suffixes,
                            normalize_before_match=self.normalize_before_match,
                        ),
                        self.token_aliases,
                    )
                    exp_can = StringProcessing.expand_token_aliases(
                        StringProcessing.normalize(
                            entry.canonical_name,
                            strip_suffixes=self.strip_suffixes,
                            normalize_before_match=self.normalize_before_match,
                        ),
                        self.token_aliases,
                    )
                    score = fuzz.WRatio(exp_raw, exp_can)
                    method = "FUZZY_WRATIO"

            mappings.append(
                VendorMapping(
                    raw_vendor_name=entry.raw_name,
                    canonical_vendor_name=entry.canonical_name,
                    match_score=round(score, 2),
                    match_method=method,
                    resolution_run_id=run_id,
                    vat_number=canonical_vat.get(entry.canonical_name),
                )
            )

        unique_canonical = len({m.canonical_vendor_name for m in mappings})
        logger.info(
            "Resolution complete: %d raw → %d canonical vendors.",
            len(unique_names), unique_canonical,
        )
        return mappings

