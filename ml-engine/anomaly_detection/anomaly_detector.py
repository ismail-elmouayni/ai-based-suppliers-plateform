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
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from typing import NamedTuple

from anomaly_detection.anomaly_flag import AnomalyFlag, Severity
from config_types import AnomalyConfig
from data_source_columns import DataSourceColumns

logger = logging.getLogger(__name__)

# Intermediate feature column names (internal to _build_features)
_SPEND_GAP     = "SpendGap"
_SPEND_GAP_PCT = "SpendGapPct"


class _AnomalyFeatures(NamedTuple):
    """Feature matrix and spend-gap signal produced by _build_features."""
    feature_matrix: pd.DataFrame  # NaN-imputed inputs for IsolationForest (columns: SpendGap, SpendGapPct, Spend, Saving_Pct)
    spend_gap:      pd.Series     # raw SpendGap per PO (used for Z-score computation)


class AnomalyDetector:
    def __init__(self, config: dict[str, Any]) -> None:
        cfg = AnomalyConfig.from_dict(config)
        self.contamination      = cfg.contamination_factor
        self.severity_high_z    = cfg.severity_high_zscore
        self.severity_medium_z  = cfg.severity_medium_zscore
        self.n_estimators       = cfg.n_estimators
        self.random_state       = cfg.random_state

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    def _build_features(self, df: pd.DataFrame) -> _AnomalyFeatures:
        feat = df.copy()

        feat[_SPEND_GAP] = feat[DataSourceColumns.SPEND].fillna(0) - feat[DataSourceColumns.ORIGINAL_SPEND].fillna(0)

        original_spend = feat[DataSourceColumns.ORIGINAL_SPEND].fillna(0).abs().replace(0, np.nan)
        feat[_SPEND_GAP_PCT] = (feat[_SPEND_GAP] / original_spend).clip(-10, 10).fillna(0)

        feature_cols = [_SPEND_GAP, _SPEND_GAP_PCT, DataSourceColumns.SPEND, DataSourceColumns.SAVING_PERCENT]
        X = feat[feature_cols].copy()

        for col in feature_cols:
            median = X[col].median()
            X[col] = X[col].fillna(0 if pd.isna(median) else median)

        return _AnomalyFeatures(feature_matrix=X, spend_gap=feat[_SPEND_GAP])

    # ------------------------------------------------------------------
    # Z-score severity
    # ------------------------------------------------------------------

    def _compute_zscores(self, df: pd.DataFrame, spend_gap: pd.Series) -> pd.Series:
        """Z-score per (CanonicalVendorName, Category) group; fallback to global."""
        z = pd.Series(0.0, index=df.index)

        group_cols = []
        if DataSourceColumns.CANONICAL_VENDOR in df.columns:
            group_cols.append(DataSourceColumns.CANONICAL_VENDOR)
        if DataSourceColumns.CATEGORY in df.columns:
            group_cols.append(DataSourceColumns.CATEGORY)

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

    def _assign_severity(self, z: float) -> Severity:
        az = abs(z)
        if az >= self.severity_high_z:
            return Severity.HIGH
        if az >= self.severity_medium_z:
            return Severity.MEDIUM
        return Severity.LOW

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, df: pd.DataFrame, run_id: int) -> list[AnomalyFlag]:
        """
        Detect anomalous POs in *df*.

        Required columns: Id, PO_Number, CanonicalVendorName, Category,
                          Original_Spend, Spend, Saving_Pct.
        Returns a typed list of AnomalyFlag objects.
        """
        if df.empty:
            logger.warning("detect() called with empty DataFrame.")
            return []

        if len(df) < 5:
            logger.warning("Too few records for reliable anomaly detection.")
            return []

        features = self._build_features(df)

        iso = IsolationForest(
            contamination=self.contamination,
            n_estimators=self.n_estimators,
            random_state=self.random_state,
        )
        iso.fit(features.feature_matrix)
        raw_scores  = iso.score_samples(features.feature_matrix)  # negative; more negative = more anomalous
        predictions = iso.predict(features.feature_matrix)        # −1 = anomaly

        # Normalise score to [0, 1] (1 = most anomalous)
        score_range = raw_scores.max() - raw_scores.min()
        anomaly_scores = (
            (raw_scores.max() - raw_scores) / score_range
            if score_range > 0
            else np.zeros(len(raw_scores))
        )

        z_scores = self._compute_zscores(df, features.spend_gap)

        flags: list[AnomalyFlag] = []

        for pos, idx in enumerate(df.index):
            if predictions[pos] == -1:
                flag = AnomalyFlag.from_detection(
                    run_id=run_id,
                    row=df.loc[idx],
                    spend_gap=float(features.spend_gap.loc[idx]),
                    anomaly_score=float(anomaly_scores[pos]),
                    z_score=float(z_scores.loc[idx]),
                    severity=self._assign_severity(float(z_scores.loc[idx])),
                )
                flags.append(flag)

        logger.info(
            f"Anomaly detection complete: {len(flags)} flags out of {len(df)} records "
            f"(contamination={self.contamination})."
        )
        return flags
