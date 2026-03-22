"""
AnomalyDetector — IsolationForest + Z-score anomaly detection for procurement POs.

Features per PO:
  SpendGap        = Spend − Original_Spend
  SpendGapPct     = SpendGap / |Original_Spend|  clipped to [−10, 10]
  Spend           = raw final spend
  Saving_Pct      = normalised saving rate

NaN → column median before model fitting.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

logger = logging.getLogger(__name__)

SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"


class AnomalyDetector:
    def __init__(self, config: dict):
        ad_cfg = config.get("anomaly_detection", {})
        self.contamination = float(ad_cfg.get("contamination_factor", 0.05))
        self.severity_high_z = float(ad_cfg.get("severity_high_zscore", 3.0))
        self.severity_medium_z = float(ad_cfg.get("severity_medium_zscore", 2.0))
        self.n_estimators = int(ad_cfg.get("n_estimators", 100))
        self.random_state = int(ad_cfg.get("random_state", 42))

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        feat = df.copy()

        # Spend gap
        feat["SpendGap"] = feat["Spend"].fillna(0) - feat["Original_Spend"].fillna(0)

        # SpendGapPct — handle zero original spend
        orig = feat["Original_Spend"].fillna(0).abs().replace(0, np.nan)
        feat["SpendGapPct"] = (feat["SpendGap"] / orig).clip(-10, 10).fillna(0)

        feature_cols = ["SpendGap", "SpendGapPct", "Spend", "Saving_Pct"]
        X = feat[feature_cols].copy()

        # Replace NaN with column median
        for col in feature_cols:
            median = X[col].median()
            X[col] = X[col].fillna(0 if pd.isna(median) else median)

        return X, feat["SpendGap"]

    # ------------------------------------------------------------------
    # Z-score severity
    # ------------------------------------------------------------------

    def _compute_zscores(self, df: pd.DataFrame, spend_gap: pd.Series) -> pd.Series:
        """Z-score per (CanonicalVendorName, Category) group; fallback to global."""
        z = pd.Series(0.0, index=df.index)

        group_cols = []
        if "CanonicalVendorName" in df.columns:
            group_cols.append("CanonicalVendorName")
        if "Category" in df.columns:
            group_cols.append("Category")

        if group_cols:
            grouped = df.groupby(group_cols, group_keys=False)
            for name, group in grouped:
                if len(group) >= 3:
                    mu = spend_gap.loc[group.index].mean()
                    sigma = spend_gap.loc[group.index].std()
                    if sigma and sigma > 0:
                        z.loc[group.index] = (spend_gap.loc[group.index] - mu) / sigma
                    # else z stays 0

        # Fallback to global z-score for groups with < 3 records
        mask = z == 0.0
        if mask.sum() > 1:
            mu_g = spend_gap[mask].mean()
            sigma_g = spend_gap[mask].std()
            if sigma_g and sigma_g > 0:
                z.loc[mask] = (spend_gap[mask] - mu_g) / sigma_g

        return z

    def _assign_severity(self, z: float) -> str:
        az = abs(z)
        if az >= self.severity_high_z:
            return SEVERITY_HIGH
        if az >= self.severity_medium_z:
            return SEVERITY_MEDIUM
        return SEVERITY_LOW

    # ------------------------------------------------------------------
    # Reason string
    # ------------------------------------------------------------------

    @staticmethod
    def _reason_string(
        row: pd.Series, z: float, vendor: str, category: str
    ) -> str:
        gap = float(row["SpendGap"])
        orig = float(row.get("Original_Spend") or 0)
        pct = (gap / abs(orig) * 100) if orig != 0 else 0.0
        direction = "exceeds original" if gap > 0 else "below original"
        cat_str = f"{vendor} - {category}" if category else vendor
        return (
            f"Spend {direction} by {abs(pct):.1f}% "
            f"({abs(gap):.2f} absolute); "
            f"{abs(z):.1f}\u03c3 above {cat_str} mean gap"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, df: pd.DataFrame, run_id: int) -> pd.DataFrame:
        """
        Detect anomalous POs in *df*.

        Required columns: Id, PO_Number, CanonicalVendorName, Category,
                          Original_Spend, Spend, Saving_Pct.
        Returns a DataFrame ready for DataRepository.write_anomaly_flags().
        """
        if df.empty:
            logger.warning("detect() called with empty DataFrame.")
            return pd.DataFrame()

        if len(df) < 5:
            logger.warning("Too few records for reliable anomaly detection.")
            return pd.DataFrame()

        X, spend_gap = self._build_features(df)

        # IsolationForest
        iso = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
        )
        iso.fit(X)
        raw_scores = iso.score_samples(X)   # negative; more negative = more anomalous
        predictions = iso.predict(X)        # −1 = anomaly

        # Normalise score to [0, 1] (1 = most anomalous)
        score_range = raw_scores.max() - raw_scores.min()
        if score_range > 0:
            anomaly_scores = (raw_scores.max() - raw_scores) / score_range
        else:
            anomaly_scores = np.zeros(len(raw_scores))

        # Z-scores
        z_scores = self._compute_zscores(df, spend_gap)

        # Build output for flagged rows (predictions == -1)
        flagged_mask = predictions == -1
        df_positions = {idx: pos for pos, idx in enumerate(df.index)}

        rows = []
        for idx in df.index[flagged_mask]:
            row = df.loc[idx]
            z = float(z_scores.loc[idx])
            vendor = str(row.get("CanonicalVendorName", ""))
            category = str(row.get("Category") or "")
            gap = float(spend_gap.loc[idx])

            rows.append(
                {
                    "RunId": run_id,
                    "SourceRecordId": row.get("Id"),
                    "PO_Number": row.get("PO_Number"),
                    "CanonicalVendorName": vendor,
                    "Category": category if category not in {"None", "nan", ""} else None,
                    "Original_Spend": row.get("Original_Spend"),
                    "Spend": row.get("Spend"),
                    "SpendGap": gap,
                    "AnomalyScore": round(float(anomaly_scores[df_positions[idx]]), 6),
                    "ZScore": round(z, 4),
                    "Severity": self._assign_severity(z),
                    "ReasonString": "",  # populated in the loop below
                }
            )

        # Build reason strings now that SpendGap is available in each row dict
        for r in rows:
            orig = r.get("Original_Spend") or 0
            gap = r["SpendGap"]
            pct = (gap / abs(orig) * 100) if orig != 0 else 0.0
            direction = "exceeds original" if gap > 0 else "below original"
            vendor = r["CanonicalVendorName"]
            cat = r["Category"] or ""
            cat_str = f"{vendor} - {cat}" if cat else vendor
            r["ReasonString"] = (
                f"Spend {direction} by {abs(pct):.1f}% "
                f"({abs(gap):.2f} absolute); "
                f"{abs(r['ZScore']):.1f}\u03c3 above {cat_str} mean gap"
            )

        result = pd.DataFrame(rows)
        logger.info(
            f"Anomaly detection complete: {len(result)} flags out of {len(df)} records "
            f"(contamination={self.contamination})."
        )
        return result
