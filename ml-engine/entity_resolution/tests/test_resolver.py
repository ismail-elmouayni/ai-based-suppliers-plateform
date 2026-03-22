"""Unit tests for VendorResolver."""

import pytest
import pandas as pd
from entity_resolution.resolver import VendorResolver

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
        rows.append({"Vendor": v, "PO_Number": f"{po_prefix}-{i:03d}"})
    return pd.DataFrame(rows)


class TestVendorResolver:
    def setup_method(self):
        self.resolver = VendorResolver(CONFIG)

    def test_exact_match_self(self):
        """A vendor resolves to itself."""
        df = make_df(["SIEMENS AG"])
        result = self.resolver.resolve(df)
        assert result.loc[result["RawVendorName"] == "SIEMENS AG", "CanonicalVendorName"].iloc[0] == "SIEMENS AG"

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
                rows.append({"Vendor": v, "PO_Number": f"PO-{v[:4]}-{j}"})
        df = pd.DataFrame(rows)
        result = self.resolver.resolve(df)

        canonicals = set(result["CanonicalVendorName"].unique())
        # All variants should share the same canonical
        mapped = result.set_index("RawVendorName")["CanonicalVendorName"]
        canonical_set = {mapped[v] for v in variants if v in mapped}
        assert len(canonical_set) == 1, f"Expected 1 canonical, got {canonical_set}"

    def test_tigmad_construction_resolves(self):
        """TIGMAD CONSTRUCTION and TIGMAD CONSTRUCTION SARL resolve together."""
        variants = ["TIGMAD CONSTRUCTION", "TIGMAD CONSTRUCTION SARL"]
        # More POs for plain name
        rows = []
        for j in range(5):
            rows.append({"Vendor": "TIGMAD CONSTRUCTION", "PO_Number": f"PO-TIG-{j}"})
        rows.append({"Vendor": "TIGMAD CONSTRUCTION SARL", "PO_Number": "PO-TIG-S-0"})
        df = pd.DataFrame(rows)
        result = self.resolver.resolve(df)
        mapped = result.set_index("RawVendorName")["CanonicalVendorName"]
        assert mapped["TIGMAD CONSTRUCTION"] == mapped["TIGMAD CONSTRUCTION SARL"]

    def test_below_threshold_stays_separate(self):
        """Two clearly different names should not be merged."""
        df = make_df(["MICROSOFT CORP", "TOTAL MAROC"])
        result = self.resolver.resolve(df)
        mapped = result.set_index("RawVendorName")["CanonicalVendorName"]
        assert mapped["MICROSOFT CORP"] != mapped["TOTAL MAROC"]

    def test_legal_suffix_stripping(self):
        """Suffix-stripped names are matched even if raw names differ by suffix only."""
        df = make_df(["ACME INDUSTRIES LTD", "ACME INDUSTRIES"])
        result = self.resolver.resolve(df)
        mapped = result.set_index("RawVendorName")["CanonicalVendorName"]
        assert mapped["ACME INDUSTRIES LTD"] == mapped["ACME INDUSTRIES"]

    def test_null_vendor_name_handled(self):
        """Rows with null Vendor are dropped gracefully."""
        df = pd.DataFrame([
            {"Vendor": None, "PO_Number": "PO-000"},
            {"Vendor": "VALID VENDOR", "PO_Number": "PO-001"},
        ])
        result = self.resolver.resolve(df)
        assert "VALID VENDOR" in result["RawVendorName"].values

    def test_result_columns(self):
        """Result DataFrame has all required columns."""
        df = make_df(["VENDOR A", "VENDOR B"])
        result = self.resolver.resolve(df)
        expected_cols = {"RawVendorName", "CanonicalVendorName", "MatchScore", "MatchMethod", "ResolutionRunId"}
        assert expected_cols.issubset(set(result.columns))

    def test_run_id_propagated(self):
        """run_id is stored in ResolutionRunId."""
        df = make_df(["VENDOR A"])
        result = self.resolver.resolve(df, run_id=42)
        assert (result["ResolutionRunId"] == 42).all()

    def test_empty_dataframe(self):
        """Empty input returns empty result without error."""
        df = pd.DataFrame(columns=["Vendor", "PO_Number"])
        result = self.resolver.resolve(df)
        assert result.empty
