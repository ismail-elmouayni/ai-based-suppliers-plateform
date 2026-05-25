
"""
core.series_processing
=============
Generic utilities for processing pandas Series in the scoring pipeline, such as normalisation.
"""

from __future__ import annotations

import pandas as pd


def normalize(series: pd.Series) -> pd.Series:
    """Min-max normalise, making series value betsween 0 and 1; returns 0.5 when min == max."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(0.5, index=series.index)
    
    return (series - mn) / (mx - mn)