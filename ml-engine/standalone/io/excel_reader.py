"""
ExcelReader
===========
Loads and validates the input ``data.xlsx`` file into a pandas DataFrame.

Expected sheet
--------------
The reader first looks for a sheet named ``ProcurementRecords``; if that sheet
is not present it falls back to the first sheet in the workbook.

Required columns
----------------
Id, Country, Vendor, Category, PO_Number, Item_Description,
Original_Spend, OPEX_CAPEX, Saving, Saving_Pct, Spend

Numeric columns that are validated / coerced
--------------------------------------------
Original_Spend, Saving, Saving_Pct, Spend
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Union

import pandas as pd

from data_source_columns import DataSourceColumns

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PREFERRED_SHEET = "ProcurementRecords"

# Canonical (internal) column names used throughout the pipeline.
REQUIRED_COLUMNS: list[str] = [
    DataSourceColumns.ID,
    DataSourceColumns.COUNTRY,
    DataSourceColumns.VENDOR,
    DataSourceColumns.CATEGORY,
    DataSourceColumns.PURCHASE_ORDERS_NUMBER,
    DataSourceColumns.ITEM_DESCRIPTION,
    DataSourceColumns.ORIGINAL_SPEND,
    DataSourceColumns.OPEX_CAPEX,
    DataSourceColumns.SAVING,
    DataSourceColumns.SAVING_PERCENT,
    DataSourceColumns.SPEND,
]

NUMERIC_COLUMNS: list[str] = [
    DataSourceColumns.ORIGINAL_SPEND,
    DataSourceColumns.SAVING,
    DataSourceColumns.SAVING_PERCENT,
    DataSourceColumns.SPEND,
]

# Maps common enterprise export column names → canonical pipeline names.
# Keys are compared case-insensitively after stripping whitespace.
COLUMN_ALIASES: dict[str, str] = {
    "po number":        DataSourceColumns.PURCHASE_ORDERS_NUMBER,
    "po_number":        DataSourceColumns.PURCHASE_ORDERS_NUMBER,
    "item description": DataSourceColumns.ITEM_DESCRIPTION,
    "item_description": DataSourceColumns.ITEM_DESCRIPTION,
    "original spend":   DataSourceColumns.ORIGINAL_SPEND,
    "original_spend":   DataSourceColumns.ORIGINAL_SPEND,
    "opex capex":       DataSourceColumns.OPEX_CAPEX,
    "opex_capex":       DataSourceColumns.OPEX_CAPEX,
    "saving %":         DataSourceColumns.SAVING_PERCENT,
    "saving_pct":       DataSourceColumns.SAVING_PERCENT,
    "saving pct":       DataSourceColumns.SAVING_PERCENT,
    "savings %":        DataSourceColumns.SAVING_PERCENT,
    "savings pct":      DataSourceColumns.SAVING_PERCENT,
    # VAT number
    "vat number":       DataSourceColumns.VAT_NUMBER,
    "vat_number":       DataSourceColumns.VAT_NUMBER,
    "vatno":            DataSourceColumns.VAT_NUMBER,
    "vat no":           DataSourceColumns.VAT_NUMBER,
    "tax id":           DataSourceColumns.VAT_NUMBER,
    "tax_id":           DataSourceColumns.VAT_NUMBER,
}

# Optional columns: present only in some sources.  ExcelReader null-fills
# them when absent so downstream code can always rely on their presence.
OPTIONAL_COLUMNS: list[str] = [
    DataSourceColumns.VAT_NUMBER,
]


# ---------------------------------------------------------------------------
# ExcelReader
# ---------------------------------------------------------------------------

class ExcelReader:
    """Reads and validates a procurement Excel file.

    Parameters
    ----------
    path:
        Path to the ``.xlsx`` input file.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If required columns are missing, the sheet is empty, or numeric
        columns cannot be coerced to float.
    """

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> pd.DataFrame:
        """Return a validated DataFrame ready for the pipeline.

        Steps
        -----
        1. Open the workbook and select the correct sheet.
        2. Normalise column names (alias mapping, whitespace, case).
        3. Auto-generate ``Id`` column if absent.
        4. Assert required columns are present.
        5. Assert the sheet is non-empty.
        6. Coerce numeric columns to float.
        7. Strip leading/trailing whitespace from string columns.
        """
        self._assert_file_exists()
        df = self._read_sheet()
        df = self._normalize_columns(df)
        df = self._ensure_id_column(df)
        self._validate_columns(df)
        self._validate_not_empty(df)
        df = self._fill_optional_columns(df)
        df = self._coerce_numerics(df)
        df = self._strip_strings(df)
        logger.info(
            "Loaded %d procurement records from '%s'.", len(df), self.path
        )
        return df

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _assert_file_exists(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(
                f"Input file not found: '{self.path}'. "
                "Please supply a valid data.xlsx path via --input."
            )

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Rename columns using COLUMN_ALIASES (case-insensitive, strip whitespace)."""
        rename_map = {}
        for col in df.columns:
            normalised = str(col).strip().lower()
            if normalised in COLUMN_ALIASES:
                rename_map[col] = COLUMN_ALIASES[normalised]
        if rename_map:
            logger.debug("Column aliases applied: %s", rename_map)
            df = df.rename(columns=rename_map)
        return df

    def _ensure_id_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add a sequential ``Id`` column when the source file has none."""
        if "Id" not in df.columns:
            logger.debug("'Id' column absent — generating sequential row IDs.")
            df = df.copy()
            df.insert(0, "Id", range(1, len(df) + 1))
        return df

    def _read_sheet(self) -> pd.DataFrame:
        """Open the workbook and return the preferred or first sheet."""
        xl = pd.ExcelFile(self.path, engine="openpyxl")
        sheet_name = (
            PREFERRED_SHEET if PREFERRED_SHEET in xl.sheet_names else xl.sheet_names[0]
        )
        logger.debug("Reading sheet '%s' from '%s'.", sheet_name, self.path)
        return xl.parse(sheet_name)

    def _validate_columns(self, df: pd.DataFrame) -> None:
        missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(
                f"Input file is missing required column(s): {missing}. "
                f"Found columns: {list(df.columns)}"
            )

    def _validate_not_empty(self, df: pd.DataFrame) -> None:
        if df.empty:
            raise ValueError(
                f"Input file '{self.path}' contains no data rows. "
                "Please provide at least one procurement record."
            )

    def _fill_optional_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Null-fill any optional columns absent from the source file."""
        df = df.copy()
        for col in OPTIONAL_COLUMNS:
            if col not in df.columns:
                df[col] = None
        return df

    def _coerce_numerics(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in NUMERIC_COLUMNS:
            try:
                df[col] = pd.to_numeric(df[col], errors="raise")
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"Column '{col}' contains non-numeric values that cannot "
                    f"be converted to float. Original error: {exc}"
                ) from exc
        return df

    def _strip_strings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Strip whitespace from object (string) columns."""
        df = df.copy()
        str_cols = df.select_dtypes(include="object").columns
        for col in str_cols:
            df[col] = df[col].astype(str).str.strip()
            # Restore genuine NaN-like values that became the string "nan"
            df[col] = df[col].replace({"nan": None, "None": None, "": None})
        return df
