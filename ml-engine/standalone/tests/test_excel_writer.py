"""
Unit tests for standalone.io.excel_writer.ExcelWriter

Strategy
--------
* Use ``xlsxwriter`` to write the output (as production code does).
* Re-open the written file with ``openpyxl`` to verify sheet names, cell
  values, and chart objects — openpyxl can read xlsxwriter-produced files.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import openpyxl
from standalone.io.excel_writer import ExcelWriter

# ---------------------------------------------------------------------------
# Minimal DataFrames for writer tests
# ---------------------------------------------------------------------------

def _make_scores_df(n: int = 6) -> pd.DataFrame:
    bands = ["GREEN", "GREEN", "AMBER", "AMBER", "RED", "INSUFFICIENT_DATA"]
    rows = []
    for i in range(n):
        rows.append({
            "RunId": 0,
            "CanonicalVendorName": f"VENDOR_{i}",
            "Category": "IT",
            "CompositeScore": 90.0 - i * 12,
            "PerformanceBand": bands[i % len(bands)],
            "SavingPctNorm": 0.8,
            "SpendNorm": 0.7,
            "SpecializationNorm": 0.9,
            "RawSavingPct": 0.15,
            "RawTotalSpend": 100_000.0,
            "RawSpecialization": 1.0,
            "POCount": 5,
        })
    return pd.DataFrame(rows)


def _make_clusters_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"RunId": 0, "ClusterLabel": 0, "DominantCategory": "IT",
         "VendorCount": 3, "TotalSpendAtStake": 500_000.0,
         "EstimatedSavingPct": 0.05, "EstimatedSavingAmount": 25_000.0},
        {"RunId": 0, "ClusterLabel": 1, "DominantCategory": "Logistics",
         "VendorCount": 2, "TotalSpendAtStake": 200_000.0,
         "EstimatedSavingPct": 0.08, "EstimatedSavingAmount": 16_000.0},
    ])


def _make_members_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"ClusterLabel": 0, "CanonicalVendorName": "VENDOR_A",
         "VendorTotalSpend": 200_000.0, "CategoriesSupplied": "IT"},
        {"ClusterLabel": 0, "CanonicalVendorName": "VENDOR_B",
         "VendorTotalSpend": 150_000.0, "CategoriesSupplied": "IT,Logistics"},
        {"ClusterLabel": 1, "CanonicalVendorName": "VENDOR_C",
         "VendorTotalSpend": 120_000.0, "CategoriesSupplied": "Logistics"},
    ])


def _make_flags_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"RunId": 0, "SourceRecordId": 1, "PO_Number": "PO-0001",
         "CanonicalVendorName": "VENDOR_A", "Category": "IT",
         "Original_Spend": 10_000.0, "Spend": 40_000.0,
         "SpendGap": 30_000.0, "AnomalyScore": 0.95, "ZScore": 4.1,
         "Severity": "HIGH", "ReasonString": "SpendGap +4.1σ above group mean"},
        {"RunId": 0, "SourceRecordId": 2, "PO_Number": "PO-0002",
         "CanonicalVendorName": "VENDOR_B", "Category": "IT",
         "Original_Spend": 15_000.0, "Spend": 30_000.0,
         "SpendGap": 15_000.0, "AnomalyScore": 0.70, "ZScore": 2.3,
         "Severity": "MEDIUM", "ReasonString": "SpendGap +2.3σ above group mean"},
    ])


def _make_mapping_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"RawVendorName": "ACME LTD",  "CanonicalVendorName": "ACME",
         "MatchScore": 100, "MatchMethod": "EXACT", "ResolutionRunId": 0},
        {"RawVendorName": "ACME CORP", "CanonicalVendorName": "ACME",
         "MatchScore": 92,  "MatchMethod": "FUZZY_WRATIO", "ResolutionRunId": 0},
    ])


def _make_raw_df() -> pd.DataFrame:
    return pd.DataFrame([
        {"Vendor": "ACME LTD",  "Category": "IT",        "Spend": 50_000.0},
        {"Vendor": "ACME CORP", "Category": "Logistics",  "Spend": 30_000.0},
        {"Vendor": "SIEMENS",   "Category": "IT",         "Spend": 80_000.0},
    ])


# ---------------------------------------------------------------------------
# Fixture: write a complete workbook and return its path
# ---------------------------------------------------------------------------

@pytest.fixture
def written_workbook(tmp_path) -> Path:
    path = tmp_path / "output.xlsx"
    with ExcelWriter(path) as writer:
        stats = {
            "total_vendors": 5,
            "total_spend": 160_000.0,
            "anomaly_count": 2,
            "cluster_count": 2,
        }
        writer.write_summary(stats, _make_raw_df())
        writer.write_entity_resolution(_make_mapping_df())
        writer.write_vendor_scores(_make_scores_df())
        writer.write_consolidation(_make_clusters_df(), _make_members_df())
        writer.write_anomaly_flags(_make_flags_df())
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExcelWriter:

    def test_output_file_created(self, written_workbook):
        """The output xlsx file is created on disk."""
        assert written_workbook.exists()
        assert written_workbook.stat().st_size > 0

    def test_all_sheets_present(self, written_workbook):
        """All 6 expected sheets are present in the workbook."""
        wb = openpyxl.load_workbook(written_workbook)
        expected = {
            "Summary", "Entity_Resolution", "Vendor_Scores",
            "Consolidation_Clusters", "Consolidation_Members", "Anomaly_Flags",
        }
        assert expected == set(wb.sheetnames)

    def test_vendor_scores_sheet_has_data_rows(self, written_workbook):
        """Vendor_Scores sheet has at least 1 data row beyond the header."""
        wb = openpyxl.load_workbook(written_workbook)
        ws = wb["Vendor_Scores"]
        # Row 1 = header; check that row 2 has content
        assert ws.max_row >= 2
        assert ws.cell(row=2, column=1).value is not None

    def test_vendor_scores_chart_embedded(self, written_workbook):
        """Vendor_Scores sheet contains at least one chart object."""
        wb = openpyxl.load_workbook(written_workbook)
        ws = wb["Vendor_Scores"]
        assert len(ws._charts) >= 1, "Expected at least 1 chart in Vendor_Scores"

    def test_consolidation_clusters_chart_embedded(self, written_workbook):
        """Consolidation_Clusters sheet contains at least one chart."""
        wb = openpyxl.load_workbook(written_workbook)
        ws = wb["Consolidation_Clusters"]
        assert len(ws._charts) >= 1

    def test_anomaly_flags_chart_embedded(self, written_workbook):
        """Anomaly_Flags sheet contains at least one chart (severity pie)."""
        wb = openpyxl.load_workbook(written_workbook)
        ws = wb["Anomaly_Flags"]
        assert len(ws._charts) >= 1

    def test_summary_sheet_has_kpi_value(self, written_workbook):
        """Summary sheet contains the total vendor count somewhere in the sheet."""
        wb = openpyxl.load_workbook(written_workbook)
        ws = wb["Summary"]
        all_values = [ws.cell(r, c).value for r in range(1, ws.max_row + 1)
                      for c in range(1, ws.max_column + 1)]
        # The KPI value for total_vendors = 5 should appear in some cell
        assert 5 in all_values

    def test_entity_resolution_has_correct_columns(self, written_workbook):
        """Entity_Resolution header row contains the expected column names."""
        wb = openpyxl.load_workbook(written_workbook)
        ws = wb["Entity_Resolution"]
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        assert "RawVendorName" in headers
        assert "CanonicalVendorName" in headers
        assert "MatchScore" in headers

    def test_anomaly_flags_severity_values_written(self, written_workbook):
        """Severity values (HIGH, MEDIUM) appear in the Anomaly_Flags sheet."""
        wb = openpyxl.load_workbook(written_workbook)
        ws = wb["Anomaly_Flags"]
        all_values = {ws.cell(r, c).value for r in range(1, ws.max_row + 1)
                      for c in range(1, ws.max_column + 1)}
        assert "HIGH" in all_values
        assert "MEDIUM" in all_values

    def test_context_manager_closes_file(self, tmp_path):
        """ExcelWriter closes cleanly when used as a context manager."""
        path = tmp_path / "test.xlsx"
        with ExcelWriter(path) as writer:
            writer.write_entity_resolution(_make_mapping_df())
        # File should be readable after context exit
        wb = openpyxl.load_workbook(path)
        assert "Entity_Resolution" in wb.sheetnames

    def test_empty_flags_df_no_chart(self, tmp_path):
        """Empty AnomalyFlags DataFrame is handled gracefully (no chart, no crash)."""
        path = tmp_path / "empty_flags.xlsx"
        empty_flags = pd.DataFrame(
            columns=["PO_Number", "CanonicalVendorName", "Category",
                     "Original_Spend", "Spend", "SpendGap",
                     "AnomalyScore", "ZScore", "Severity", "ReasonString"]
        )
        with ExcelWriter(path) as writer:
            writer.write_anomaly_flags(empty_flags)
        wb = openpyxl.load_workbook(path)
        # Sheet should exist but no chart (empty data)
        assert "Anomaly_Flags" in wb.sheetnames
        ws = wb["Anomaly_Flags"]
        assert len(ws._charts) == 0

    def test_summary_chart_embedded_when_raw_data_provided(self, written_workbook):
        """Summary sheet embeds a spend-by-category chart when raw_df is non-empty."""
        wb = openpyxl.load_workbook(written_workbook)
        ws = wb["Summary"]
        assert len(ws._charts) >= 1
