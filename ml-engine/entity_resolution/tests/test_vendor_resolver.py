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
