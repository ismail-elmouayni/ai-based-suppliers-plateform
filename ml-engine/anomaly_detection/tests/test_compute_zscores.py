"""Unit tests for AnomalyDetector._compute_zscores."""

import numpy as np
import pandas as pd

from anomaly_detection.anomaly_detector import AnomalyDetector
from data_source_columns import DataSourceColumns

CONFIG = {
    "anomaly_detection": {
        "contamination_factor": 0.10,
        "severity_high_zscore": 3.0,
        "severity_medium_zscore": 2.0,
        "n_estimators": 10,
        "random_state": 42,
    }
}


def _make_detector() -> AnomalyDetector:
    return AnomalyDetector(CONFIG)


def test_compute_zscores_groupwise_when_group_size_at_least_three():
    detector = _make_detector()

    df = pd.DataFrame(
        {
            DataSourceColumns.CANONICAL_VENDOR: ["V1", "V1", "V1", "V2", "V2", "V2"],
            DataSourceColumns.CATEGORY: ["C1", "C1", "C1", "C1", "C1", "C1"],
        }
    )
    spend_gap = pd.Series([10.0, 12.0, 18.0, 100.0, 110.0, 130.0], index=df.index)

    z = detector._compute_zscores(df, spend_gap)

    expected = pd.Series(0.0, index=df.index)
    for _, group in df.groupby([DataSourceColumns.CANONICAL_VENDOR, DataSourceColumns.CATEGORY], group_keys=False):
        grp_gap = spend_gap.loc[group.index]
        expected.loc[group.index] = (grp_gap - grp_gap.mean()) / grp_gap.std()

    assert np.allclose(z.values, expected.values, atol=1e-12)


def test_compute_zscores_falls_back_to_global_for_small_groups():
    detector = _make_detector()

    df = pd.DataFrame(
        {
            DataSourceColumns.CANONICAL_VENDOR: ["V1", "V1", "V2", "V2"],
            DataSourceColumns.CATEGORY: ["C1", "C2", "C1", "C2"],
        }
    )
    spend_gap = pd.Series([5.0, 9.0, 13.0, 17.0], index=df.index)

    z = detector._compute_zscores(df, spend_gap)

    expected = (spend_gap - spend_gap.mean()) / spend_gap.std()
    assert np.allclose(z.values, expected.values, atol=1e-12)


def test_compute_zscores_uses_global_when_group_columns_missing():
    detector = _make_detector()

    # No CanonicalVendorName/Category columns means full-series global fallback.
    df = pd.DataFrame({"Other": [1, 2, 3, 4]})
    spend_gap = pd.Series([20.0, 25.0, 40.0, 55.0], index=df.index)

    z = detector._compute_zscores(df, spend_gap)

    expected = (spend_gap - spend_gap.mean()) / spend_gap.std()
    assert np.allclose(z.values, expected.values, atol=1e-12)


def test_compute_zscores_returns_zero_when_variance_is_zero():
    detector = _make_detector()

    df = pd.DataFrame(
        {
            DataSourceColumns.CANONICAL_VENDOR: ["V1", "V1", "V1", "V1"],
            DataSourceColumns.CATEGORY: ["C1", "C1", "C1", "C1"],
        }
    )
    spend_gap = pd.Series([7.0, 7.0, 7.0, 7.0], index=df.index)

    z = detector._compute_zscores(df, spend_gap)

    assert (z == 0.0).all()
