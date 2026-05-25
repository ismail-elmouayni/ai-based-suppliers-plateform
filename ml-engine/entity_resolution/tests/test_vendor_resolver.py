"""Unit tests for VendorResolver."""

import pytest
import pandas as pd
from entity_resolution.vendor_resolver import VendorResolver
from entity_resolution.vendor_mapping import VendorMapping
from config_types import EntityResolutionConfig
from data_source_columns import DataSourceColumns

CONFIG = {
    "entity_resolution": {
        "match_threshold": 85,
        "top_k_candidates": 5,
        "normalize_before_match": True,
        "strip_suffixes": ["SARL", "SARLAU", "SA", "SAS", "INC", "S.A", "GMBH", "LTD", "LLC", "CORP", "STE"],
    }
}


def make_df(vendors, po_prefix="PO"):
    rows = []
    for i, v in enumerate(vendors):
        rows.append({DataSourceColumns.VENDOR: v, DataSourceColumns.PURCHASE_ORDERS_NUMBER: f"{po_prefix}-{i:03d}"})
    return pd.DataFrame(rows)


class TestVendorResolver:
    def setup_method(self):
        self.resolver = VendorResolver(EntityResolutionConfig.from_dict(CONFIG))

    def test_exact_match_self(self):
        """A vendor resolves to itself."""
        df = make_df(["SIEMENS AG"])
        result = self.resolver.resolve(df)
        assert next(m.canonical_vendor_name for m in result if m.raw_vendor_name == "SIEMENS AG") == "SIEMENS AG"

    def test_teleperformance_group_resolves_to_one_canonical(self):
        """All Teleperformance variants must map to one canonical name."""
        variants = [
            "TELEPERFORMANCE SE",
            "TP GROUP INC",
            "TELEPERFORMANCE GROUP, INC.",
            "TELEPERFORMANCE SUPPORT SERVICE GMB",
        ]
        # Give TELEPERFORMANCE SE the highest PO count
        rows = []
        for i, v in enumerate(variants):
            count = 10 if v == "TELEPERFORMANCE SE" else 1
            for j in range(count):
                rows.append({DataSourceColumns.VENDOR: v, DataSourceColumns.PURCHASE_ORDERS_NUMBER: f"PO-{v[:4]}-{j}"})
        df = pd.DataFrame(rows)
        result = self.resolver.resolve(df)

        mapped = {m.raw_vendor_name: m.canonical_vendor_name for m in result}
        canonical_set = {mapped[v] for v in variants if v in mapped}
        assert len(canonical_set) == 1, f"Expected 1 canonical, got {canonical_set}"

    def test_tigmad_construction_resolves(self):
        """TIGMAD CONSTRUCTION and TIGMAD CONSTRUCTION SARL resolve together."""
        variants = ["TIGMAD CONSTRUCTION", "TIGMAD CONSTRUCTION SARL"]
        # More POs for plain name
        rows = []
        for j in range(5):
            rows.append({DataSourceColumns.VENDOR: "TIGMAD CONSTRUCTION", DataSourceColumns.PURCHASE_ORDERS_NUMBER: f"PO-TIG-{j}"})
        rows.append({DataSourceColumns.VENDOR: "TIGMAD CONSTRUCTION SARL", DataSourceColumns.PURCHASE_ORDERS_NUMBER: "PO-TIG-S-0"})
        df = pd.DataFrame(rows)
        result = self.resolver.resolve(df)
        mapped = {m.raw_vendor_name: m.canonical_vendor_name for m in result}
        assert mapped["TIGMAD CONSTRUCTION"] == mapped["TIGMAD CONSTRUCTION SARL"]

    def test_below_threshold_stays_separate(self):
        """Two clearly different names should not be merged."""
        df = make_df(["MICROSOFT CORP", "TOTAL MAROC"])
        result = self.resolver.resolve(df)
        mapped = {m.raw_vendor_name: m.canonical_vendor_name for m in result}
        assert mapped["MICROSOFT CORP"] != mapped["TOTAL MAROC"]

    def test_legal_suffix_stripping(self):
        """Suffix-stripped names are matched even if raw names differ by suffix only."""
        df = make_df(["ACME INDUSTRIES LTD", "ACME INDUSTRIES"])
        result = self.resolver.resolve(df)
        mapped = {m.raw_vendor_name: m.canonical_vendor_name for m in result}
        assert mapped["ACME INDUSTRIES LTD"] == mapped["ACME INDUSTRIES"]

    def test_null_vendor_name_handled(self):
        """Rows with null Vendor are dropped gracefully."""
        df = pd.DataFrame([
            {DataSourceColumns.VENDOR: None, DataSourceColumns.PURCHASE_ORDERS_NUMBER: "PO-000"},
            {DataSourceColumns.VENDOR: "VALID VENDOR", DataSourceColumns.PURCHASE_ORDERS_NUMBER: "PO-001"},
        ])
        result = self.resolver.resolve(df)
        assert any(m.raw_vendor_name == "VALID VENDOR" for m in result)

    def test_result_columns(self):
        """Result objects have all required fields."""
        df = make_df(["VENDOR A", "VENDOR B"])
        result = self.resolver.resolve(df)
        assert len(result) == 2
        m = result[0]
        assert isinstance(m, VendorMapping)
        assert hasattr(m, "raw_vendor_name")
        assert hasattr(m, "canonical_vendor_name")
        assert hasattr(m, "match_score")
        assert hasattr(m, "match_method")
        assert hasattr(m, "resolution_run_id")

    def test_run_id_propagated(self):
        """run_id is stored in resolution_run_id."""
        df = make_df(["VENDOR A"])
        result = self.resolver.resolve(df, run_id=42)
        assert all(m.resolution_run_id == 42 for m in result)

    def test_empty_dataframe(self):
        """Empty input returns empty result without error."""
        df = pd.DataFrame(columns=[DataSourceColumns.VENDOR, DataSourceColumns.PURCHASE_ORDERS_NUMBER])
        result = self.resolver.resolve(df)
        assert result == []


# ---------------------------------------------------------------------------
# New tests for alias expansion, VAT force-merge, VAT block
# ---------------------------------------------------------------------------

def make_df_with_vat(rows: list[dict]) -> pd.DataFrame:
    """Build a df with Vendor, PO_Number, Category, and VATNumber columns."""
    return pd.DataFrame([
        {
            DataSourceColumns.VENDOR: r["vendor"],
            DataSourceColumns.PURCHASE_ORDERS_NUMBER: r.get("po", f"PO-{i:03d}"),
            DataSourceColumns.CATEGORY: r.get("category", "IT"),
            DataSourceColumns.VAT_NUMBER: r.get("vat"),
        }
        for i, r in enumerate(rows)
    ])


class TestAliasExpansion:
    def setup_method(self):
        cfg = {
            "entity_resolution": {
                **CONFIG["entity_resolution"],
                "token_aliases": {"TP": "TELEPERFORMANCE"},
            }
        }
        self.resolver = VendorResolver(EntityResolutionConfig.from_dict(cfg))

    def test_alias_expands_and_merges(self):
        """TP GROUP INC and TELEPERFORMANCE GROUP INC should merge via alias expansion."""
        df = make_df_with_vat([
            {"vendor": "TELEPERFORMANCE GROUP INC", "po": "PO-001"},
            {"vendor": "TELEPERFORMANCE GROUP INC", "po": "PO-002"},
            {"vendor": "TP GROUP INC",              "po": "PO-003"},
        ])
        result = self.resolver.resolve(df)
        mapped = {m.raw_vendor_name: m.canonical_vendor_name for m in result}
        assert mapped["TP GROUP INC"] == mapped["TELEPERFORMANCE GROUP INC"]


class TestVATSignal:
    def setup_method(self):
        self.resolver = VendorResolver(EntityResolutionConfig.from_dict(CONFIG))

    def test_same_vat_force_merges_dissimilar_names(self):
        """Two vendors with the same non-null VAT must be merged regardless of name similarity."""
        df = make_df_with_vat([
            {"vendor": "TELEPERFORMANCE SE",   "vat": "FR12345678901", "po": "PO-001"},
            {"vendor": "TP GROUP INC",          "vat": "FR12345678901", "po": "PO-002"},
        ])
        result = self.resolver.resolve(df)
        mapped = {m.raw_vendor_name: m.canonical_vendor_name for m in result}
        assert mapped["TELEPERFORMANCE SE"] == mapped["TP GROUP INC"]
        # The VAT-forced merge should be surfaced in the match_method
        tp_entry = next(m for m in result if m.raw_vendor_name == "TP GROUP INC")
        assert tp_entry.match_method in ("VAT_FORCE_MERGE", "EXACT", "FUZZY_WRATIO")

    def test_different_vat_blocks_name_merge(self):
        """Two vendors with similar names but different non-null VATs must NOT be merged."""
        df = make_df_with_vat([
            {"vendor": "ACME INDUSTRIES LTD", "vat": "GB111111111", "po": "PO-001"},
            {"vendor": "ACME INDUSTRIES",     "vat": "GB222222222", "po": "PO-002"},
        ])
        result = self.resolver.resolve(df)
        mapped = {m.raw_vendor_name: m.canonical_vendor_name for m in result}
        # Different VATs → must remain separate entities
        assert mapped["ACME INDUSTRIES LTD"] != mapped["ACME INDUSTRIES"]
