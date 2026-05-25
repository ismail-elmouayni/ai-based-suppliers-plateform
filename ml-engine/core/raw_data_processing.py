"""
core.raw_data
=============
Generic utilities for working with raw procurement DataFrames before
they reach any domain-specific pipeline step.
"""

from __future__ import annotations

import pandas as pd


class RawDataProcessing:
    """Shared constants and helpers for raw input DataFrames."""

    NULL_VALUES: frozenset[str] = frozenset({"NULL", "None", "nan", ""})

    @staticmethod
    def drop_null_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
        """Return *df* with rows removed where *column* is NaN or a null sentinel string.

        Combines a pandas ``notna()`` check with a string-sentinel check so
        that both actual ``NaN`` and string representations like ``"NULL"``
        or ``"nan"`` are treated as missing.
        """
        df = df[df[column].notna()]
        df = df[~df[column].astype(str).isin(RawDataProcessing.NULL_VALUES)]
        
        return df.copy()
