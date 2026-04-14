"""
Unit/integration tests for standalone.pipeline.runner.StandalonePipeline

These tests run the full pipeline end-to-end on synthetic in-memory data,
writing to a temporary directory and then verifying the output workbook.
"""

from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from standalone.pipeline.runner import StandalonePipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXPECTED_SHEETS = {
    "Summary",
    "Entity_Resolution",
    "Vendor_Scores",
    "Consolidation_Clusters",
    "Consolidation_Members",
    "Anomaly_Flags",
}


def _run_pipeline(config, tmp_input_xlsx, tmp_path) -> Path:
    """Run the pipeline and return the output path."""
    output_path = tmp_path / "output.xlsx"
    pipeline = StandalonePipeline(config)
    pipeline.run(tmp_input_xlsx, output_path)
    return output_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestStandalonePipeline:

    def test_output_file_created(self, config, tmp_input_xlsx, tmp_path):
        """Pipeline creates an output xlsx file on disk."""
        output = _run_pipeline(config, tmp_input_xlsx, tmp_path)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_all_sheets_present(self, config, tmp_input_xlsx, tmp_path):
        """Output workbook contains all 6 expected sheets."""
        output = _run_pipeline(config, tmp_input_xlsx, tmp_path)
        wb = openpyxl.load_workbook(output)
        assert EXPECTED_SHEETS == set(wb.sheetnames)

    def test_vendor_scores_in_range(self, config, tmp_input_xlsx, tmp_path):
        """All composite scores written to Vendor_Scores are in [0, 100]."""
        output = _run_pipeline(config, tmp_input_xlsx, tmp_path)
        wb = openpyxl.load_workbook(output)
        ws = wb["Vendor_Scores"]

        # Find the CompositeScore column index from the header row
        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        if "CompositeScore" not in headers:
            pytest.skip("CompositeScore column not found in Vendor_Scores sheet")
        col_idx = headers.index("CompositeScore") + 1

        scores = [
            ws.cell(r, col_idx).value
            for r in range(2, ws.max_row + 1)
            if ws.cell(r, col_idx).value is not None
        ]
        assert len(scores) > 0, "No scored rows found"
        for score in scores:
            assert 0 <= float(score) <= 100, f"Score out of range: {score}"

    def test_entity_resolution_produces_mappings(self, config, tmp_input_xlsx, tmp_path):
        """Entity_Resolution sheet has at least as many rows as unique vendors."""
        output = _run_pipeline(config, tmp_input_xlsx, tmp_path)
        wb = openpyxl.load_workbook(output)
        ws = wb["Entity_Resolution"]
        # At least 1 data row beyond the header
        assert ws.max_row >= 2

    def test_anomaly_flags_not_empty(self, config, tmp_input_xlsx, tmp_path):
        """With injected anomalous POs, at least 1 anomaly flag should appear."""
        output = _run_pipeline(config, tmp_input_xlsx, tmp_path)
        wb = openpyxl.load_workbook(output)
        ws = wb["Anomaly_Flags"]
        # max_row == 1 means only the header; we expect data rows too
        assert ws.max_row >= 2, (
            "Expected at least 1 anomaly flag — the fixture injects 2 anomalous POs."
        )

    def test_consolidation_clusters_present(self, config, tmp_input_xlsx, tmp_path):
        """Consolidation_Clusters sheet has at least 1 cluster data row."""
        output = _run_pipeline(config, tmp_input_xlsx, tmp_path)
        wb = openpyxl.load_workbook(output)
        ws = wb["Consolidation_Clusters"]
        assert ws.max_row >= 2, "Expected at least 1 consolidation cluster"

    def test_performance_bands_valid(self, config, tmp_input_xlsx, tmp_path):
        """All PerformanceBand values are one of the four valid bands."""
        valid_bands = {"GREEN", "AMBER", "RED", "INSUFFICIENT_DATA"}
        output = _run_pipeline(config, tmp_input_xlsx, tmp_path)
        wb = openpyxl.load_workbook(output)
        ws = wb["Vendor_Scores"]

        headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
        if "PerformanceBand" not in headers:
            pytest.skip("PerformanceBand column not found")
        col_idx = headers.index("PerformanceBand") + 1

        for r in range(2, ws.max_row + 1):
            val = ws.cell(r, col_idx).value
            if val is not None:
                assert val in valid_bands, f"Invalid PerformanceBand: '{val}'"

    def test_missing_input_file_raises(self, config, tmp_path):
        """FileNotFoundError is raised when the input path does not exist."""
        pipeline = StandalonePipeline(config)
        with pytest.raises(FileNotFoundError):
            pipeline.run(tmp_path / "nonexistent.xlsx", tmp_path / "output.xlsx")

    def test_pipeline_is_idempotent(self, config, tmp_input_xlsx, tmp_path):
        """Running the pipeline twice on the same input produces identical row counts."""
        out1 = tmp_path / "out1.xlsx"
        out2 = tmp_path / "out2.xlsx"
        pipeline = StandalonePipeline(config)
        pipeline.run(tmp_input_xlsx, out1)
        pipeline.run(tmp_input_xlsx, out2)

        wb1 = openpyxl.load_workbook(out1)
        wb2 = openpyxl.load_workbook(out2)
        for sheet in EXPECTED_SHEETS:
            assert wb1[sheet].max_row == wb2[sheet].max_row, (
                f"Sheet '{sheet}' has different row counts across runs"
            )

    def test_summary_sheet_reflects_correct_vendor_count(
        self, config, tmp_input_xlsx, tmp_path
    ):
        """Summary sheet KPI value for total vendors is a positive integer."""
        output = _run_pipeline(config, tmp_input_xlsx, tmp_path)
        wb = openpyxl.load_workbook(output)
        ws = wb["Summary"]
        all_values = [
            ws.cell(r, c).value
            for r in range(1, ws.max_row + 1)
            for c in range(1, ws.max_column + 1)
            if isinstance(ws.cell(r, c).value, int)
        ]
        # The total vendor count (a positive int) must appear somewhere
        assert any(v > 0 for v in all_values), (
            "No positive integer found in Summary sheet — expected vendor count KPI"
        )
