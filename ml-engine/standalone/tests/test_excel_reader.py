"""
Unit tests for standalone.io.excel_reader.ExcelReader
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure workspace root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from standalone.io.excel_reader import ExcelReader, REQUIRED_COLUMNS
from data_source_columns import DataSourceColumns


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_xlsx(path: Path, df: pd.DataFrame, sheet_name: str = "ProcurementRecords") -> Path:
    df.to_excel(path, index=False, sheet_name=sheet_name)
    return path


def _minimal_row(**overrides) -> dict:
    base = {
        DataSourceColumns.ID: 1,
        DataSourceColumns.COUNTRY: "FR",
        DataSourceColumns.VENDOR: "ACME",
        DataSourceColumns.CATEGORY: "IT",
        DataSourceColumns.PURCHASE_ORDERS_NUMBER: "PO-0001",
        DataSourceColumns.ITEM_DESCRIPTION: "Widget",
        DataSourceColumns.ORIGINAL_SPEND: 10000.0,
        DataSourceColumns.OPEX_CAPEX: "OPEX",
        DataSourceColumns.SAVING: 500.0,
        DataSourceColumns.SAVING_PERCENT: 0.05,
        DataSourceColumns.SPEND: 9500.0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExcelReader:

    def test_load_valid_file(self, tmp_path, sample_procurement_df):
        """Loads a valid xlsx and returns a DataFrame with all required columns."""
        path = _write_xlsx(tmp_path / "data.xlsx", sample_procurement_df)
        df = ExcelReader(path).load()

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        for col in REQUIRED_COLUMNS:
            assert col in df.columns, f"Missing column: {col}"

    def test_preferred_sheet_used(self, tmp_path, sample_procurement_df):
        """Reader selects the 'ProcurementRecords' sheet when it exists."""
        path = _write_xlsx(tmp_path / "data.xlsx", sample_procurement_df, "ProcurementRecords")
        df = ExcelReader(path).load()
        assert len(df) == len(sample_procurement_df)

    def test_fallback_to_first_sheet(self, tmp_path, sample_procurement_df):
        """Falls back to the first sheet when 'ProcurementRecords' is absent."""
        path = _write_xlsx(tmp_path / "data.xlsx", sample_procurement_df, "Sheet1")
        df = ExcelReader(path).load()
        assert len(df) == len(sample_procurement_df)

    def test_missing_column_raises_value_error(self, tmp_path, sample_procurement_df):
        """Raises ValueError naming the missing column."""
        df_bad = sample_procurement_df.drop(columns=["Spend"])
        path = _write_xlsx(tmp_path / "bad.xlsx", df_bad)
        with pytest.raises(ValueError, match="Spend"):
            ExcelReader(path).load()

    def test_multiple_missing_columns_raises(self, tmp_path, sample_procurement_df):
        """Raises ValueError when multiple required columns are missing."""
        df_bad = sample_procurement_df.drop(columns=["Spend", "Saving_Pct", "Category"])
        path = _write_xlsx(tmp_path / "bad.xlsx", df_bad)
        with pytest.raises(ValueError):
            ExcelReader(path).load()

    def test_empty_sheet_raises_value_error(self, tmp_path):
        """Raises ValueError on a sheet with headers but no data rows."""
        empty_df = pd.DataFrame(columns=REQUIRED_COLUMNS)
        path = _write_xlsx(tmp_path / "empty.xlsx", empty_df)
        with pytest.raises(ValueError, match="no data rows"):
            ExcelReader(path).load()

    def test_file_not_found_raises(self, tmp_path):
        """Raises FileNotFoundError for a non-existent path."""
        with pytest.raises(FileNotFoundError):
            ExcelReader(tmp_path / "does_not_exist.xlsx").load()

    def test_numeric_columns_are_float(self, tmp_path):
        """Numeric columns (Spend, Original_Spend, Saving, Saving_Pct) are float dtype."""
        df = pd.DataFrame([_minimal_row()])
        path = _write_xlsx(tmp_path / "data.xlsx", df)
        result = ExcelReader(path).load()
        for col in ("Original_Spend", "Saving", "Saving_Pct", "Spend"):
            assert pd.api.types.is_float_dtype(result[col]) or pd.api.types.is_numeric_dtype(result[col]), \
                f"Column '{col}' is not numeric: {result[col].dtype}"

    def test_string_numerics_are_coerced(self, tmp_path):
        """Numeric columns stored as strings in Excel are coerced to float."""
        df = pd.DataFrame([_minimal_row(Spend="9500.00", Original_Spend="10000")])
        # Write as-is (strings stay strings in xlsx when using openpyxl)
        path = _write_xlsx(tmp_path / "data.xlsx", df)
        result = ExcelReader(path).load()
        assert result["Spend"].iloc[0] == pytest.approx(9500.0)

    def test_non_numeric_spend_raises(self, tmp_path):
        """Non-numeric values in a numeric column raise ValueError."""
        df = pd.DataFrame([_minimal_row(Spend="not-a-number")])
        path = _write_xlsx(tmp_path / "data.xlsx", df)
        with pytest.raises(ValueError, match="non-numeric"):
            ExcelReader(path).load()

    def test_whitespace_stripped_from_strings(self, tmp_path):
        """Leading/trailing whitespace is stripped from string columns."""
        df = pd.DataFrame([_minimal_row(Vendor="  ACME  ", Category=" IT ")])
        path = _write_xlsx(tmp_path / "data.xlsx", df)
        result = ExcelReader(path).load()
        assert result["Vendor"].iloc[0] == "ACME"
        assert result["Category"].iloc[0] == "IT"

    def test_row_count_preserved(self, tmp_path, sample_procurement_df):
        """The number of rows returned matches the number of rows in the file."""
        path = _write_xlsx(tmp_path / "data.xlsx", sample_procurement_df)
        result = ExcelReader(path).load()
        assert len(result) == len(sample_procurement_df)
