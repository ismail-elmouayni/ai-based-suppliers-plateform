"""Unit tests for AnomalyDetector."""

import pytest
import pandas as pd
import numpy as np
from anomaly_detection.detector import AnomalyDetector, SEVERITY_HIGH, SEVERITY_MEDIUM, SEVERITY_LOW

CONFIG = {
    "anomaly_detection": {
        "contamination_factor": 0.10,
        "severity_high_zscore": 3.0,
        "severity_medium_zscore": 2.0,
        "n_estimators": 10,
        "random_state": 42,
    }
}


def make_normal_df(n=50, seed=42):
    """Generate normally-distributed spend records."""
    rng = np.random.RandomState(seed)
    rows = []
    for i in range(n):
        orig = rng.uniform(10000, 100000)
        spend = orig * rng.uniform(0.90, 1.10)  # ±10% variation
        rows.append({
            "Id": i + 1,
            "PO_Number": f"PO-{i:04d}",
            "CanonicalVendorName": f"VENDOR_{i % 5}",
            "Category": f"CAT_{i % 3}",
            "Original_Spend": orig,
            "Spend": spend,
            "Saving_Pct": rng.uniform(0.05, 0.20),
        })
    return pd.DataFrame(rows)


def inject_anomaly(df, idx, multiplier=2.5):
    """Make one record's spend much higher than original."""
    df = df.copy()
    df.loc[idx, "Spend"] = df.loc[idx, "Original_Spend"] * multiplier
    return df


class TestAnomalyDetector:
    def setup_method(self):
        self.detector = AnomalyDetector(CONFIG)

    def test_flagged_count_respects_contamination(self):
        """Number of flags should be approximately contamination * n."""
        df = make_normal_df(n=100)
        result = self.detector.detect(df, run_id=1)
        expected_max = int(len(df) * 0.20)  # allow 2x tolerance
        assert len(result) <= expected_max

    def test_anomaly_score_in_range(self):
        """AnomalyScore must be in [0, 1]."""
        df = make_normal_df(n=60)
        result = self.detector.detect(df, run_id=1)
        if not result.empty:
            assert (result["AnomalyScore"] >= 0).all()
            assert (result["AnomalyScore"] <= 1).all()

    def test_severity_high_threshold(self):
        """Flag with |z| ≥ 3.0 should be HIGH."""
        detector = AnomalyDetector(CONFIG)
        assert detector._assign_severity(3.5) == SEVERITY_HIGH
        assert detector._assign_severity(-3.1) == SEVERITY_HIGH

    def test_severity_medium_threshold(self):
        """Flag with 2.0 ≤ |z| < 3.0 should be MEDIUM."""
        detector = AnomalyDetector(CONFIG)
        assert detector._assign_severity(2.5) == SEVERITY_MEDIUM
        assert detector._assign_severity(-2.0) == SEVERITY_MEDIUM

    def test_severity_low_threshold(self):
        """Flag with |z| < 2.0 should be LOW."""
        detector = AnomalyDetector(CONFIG)
        assert detector._assign_severity(1.0) == SEVERITY_LOW
        assert detector._assign_severity(0.0) == SEVERITY_LOW

    def test_reason_string_contains_sigma(self):
        """ReasonString must contain σ notation."""
        df = make_normal_df(n=60)
        result = self.detector.detect(df, run_id=1)
        if not result.empty:
            assert result["ReasonString"].str.contains("σ").any()

    def test_negative_original_spend_handled(self):
        """Rows with negative Original_Spend should not raise errors."""
        df = make_normal_df(n=20)
        df.loc[0, "Original_Spend"] = -50000.0
        df.loc[0, "Spend"] = -45000.0
        # Should run without exception
        result = self.detector.detect(df, run_id=1)
        assert isinstance(result, pd.DataFrame)

    def test_output_columns(self):
        """Output DataFrame has all required columns."""
        df = make_normal_df(n=40)
        result = self.detector.detect(df, run_id=1)
        if not result.empty:
            required = {
                "RunId", "SourceRecordId", "PO_Number", "CanonicalVendorName",
                "Category", "Original_Spend", "Spend", "SpendGap",
                "AnomalyScore", "ZScore", "Severity", "ReasonString",
            }
            assert required.issubset(set(result.columns))

    def test_empty_df_returns_empty(self):
        """Empty input returns empty DataFrame."""
        df = pd.DataFrame(columns=["Id", "PO_Number", "CanonicalVendorName", "Category",
                                    "Original_Spend", "Spend", "Saving_Pct"])
        result = self.detector.detect(df, run_id=1)
        assert result.empty
