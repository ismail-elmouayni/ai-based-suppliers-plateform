"""
Shared pytest fixtures for the standalone pipeline tests.

Fixtures
--------
config
    Full model configuration dict (mirrors model_config.yml).
sample_procurement_df
    ~35-row DataFrame with realistic procurement records including vendor name
    variants and two injected anomalous POs.
tmp_input_xlsx(tmp_path)
    Factory fixture that writes *sample_procurement_df* to a temporary xlsx
    file and returns the path.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@pytest.fixture
def config() -> dict:
    return {
        "entity_resolution": {
            "match_threshold": 85,
            "top_k_candidates": 5,
            "normalize_before_match": True,
            "strip_suffixes": [
                "SARL", "SARLAU", "SA", "SAS", "INC",
                "S.A", "GMBH", "LTD", "LLC", "CORP", "STE",
            ],
        },
        "vendor_scoring": {
            "saving_pct_weight": 0.50,
            "spend_weight": 0.30,
            "specialization_weight": 0.20,
            "min_po_count_for_scoring": 3,
            "band_green_min": 70,
            "band_amber_min": 40,
        },
        "consolidation": {
            "min_cluster_size": 2,
            "algorithm": "kmeans",
            "n_clusters": 3,
            "dbscan_eps": 0.5,
            "dbscan_min_samples": 2,
        },
        "anomaly_detection": {
            "contamination_factor": 0.10,
            "severity_high_zscore": 3.0,
            "severity_medium_zscore": 2.0,
            "n_estimators": 10,
            "random_state": 42,
        },
    }


# ---------------------------------------------------------------------------
# Synthetic procurement DataFrame
# ---------------------------------------------------------------------------

def _build_sample_df() -> pd.DataFrame:
    """Build a deterministic synthetic procurement DataFrame."""
    rng = np.random.RandomState(0)

    vendors = [
        # Three clusters of similar names to test entity resolution
        ("ACME LOGISTICS", "Logistics"),
        ("ACME LOGISTICS LTD", "Logistics"),
        ("ACME LOGISTIK", "Logistics"),
        ("TOTAL ENERGIE", "Energy"),
        ("TOTAL ENERGY INC", "Energy"),
        ("SIEMENS AG", "IT"),
        ("SIEMENS", "IT"),
        ("MICROSOFT CORP", "IT"),
        ("MICROSOFT", "IT"),
        ("ORANGE TELECOM", "Telecom"),
    ]

    rows = []
    po_counter = 0

    for vendor, category in vendors:
        n_pos = rng.randint(4, 9)  # 4–8 POs per vendor (>= min_po_count_for_scoring=3)
        for _ in range(n_pos):
            original_spend = rng.uniform(10_000, 200_000)
            spend = original_spend * rng.uniform(0.90, 1.10)
            saving = original_spend - spend
            saving_pct = saving / original_spend if original_spend else 0.0
            rows.append({
                "Id":               po_counter + 1,
                "Country":          rng.choice(["FR", "DE", "MA", "US"]),
                "Vendor":           vendor,
                "Category":         category,
                "PO_Number":        f"PO-{po_counter:04d}",
                "Item_Description": f"Item for {category}",
                "Original_Spend":   round(original_spend, 2),
                "OPEX_CAPEX":       rng.choice(["OPEX", "CAPEX"]),
                "Saving":           round(saving, 2),
                "Saving_Pct":       round(saving_pct, 4),
                "Spend":            round(spend, 2),
            })
            po_counter += 1

    df = pd.DataFrame(rows)

    # Inject two obvious anomalies (spend >> original_spend)
    df.loc[0, "Spend"] = df.loc[0, "Original_Spend"] * 4.0   # HIGH anomaly
    df.loc[1, "Spend"] = df.loc[1, "Original_Spend"] * 3.0   # MEDIUM-ish anomaly

    return df


@pytest.fixture
def sample_procurement_df() -> pd.DataFrame:
    return _build_sample_df()


# ---------------------------------------------------------------------------
# tmp_input_xlsx factory
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_input_xlsx(tmp_path, sample_procurement_df):
    """Write sample_procurement_df to a temporary xlsx and return its path."""
    path = tmp_path / "data.xlsx"
    sample_procurement_df.to_excel(path, index=False, sheet_name="ProcurementRecords")
    return path
