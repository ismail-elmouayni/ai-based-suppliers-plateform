"""
Integration tests — AI-Powered Supplier Intelligence Platform.

Requires:
  - A running SQL Server instance (SupplierIntelligenceTest database)
  - MSSQL_DATABASE env var set to 'SupplierIntelligenceTest'
  - Migrations applied + sample_data.csv seeded before running

Run:
    docker compose --profile test run test
"""

import os
import time

import pytest
import requests
import pandas as pd
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DB_HOST = os.getenv("MSSQL_HOST", "sqlserver")
DB_PORT = os.getenv("MSSQL_PORT", "1433")
DB_NAME = os.getenv("MSSQL_DATABASE", "SupplierIntelligenceTest")
DB_USER = os.getenv("MSSQL_USER", "sa")
DB_PASS = os.getenv("MSSQL_SA_PASSWORD", "")
API_BASE = os.getenv("API_BASE_URL", "http://api:8080/api/v1")
ML_BASE = os.getenv("ML_BASE_URL", "http://ml-engine:5001")

DRIVER = "ODBC+Driver+18+for+SQL+Server"
CONN_URL = (
    f"mssql+pyodbc://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?driver={DRIVER}&TrustServerCertificate=yes&Encrypt=yes"
)


@pytest.fixture(scope="session")
def engine():
    return create_engine(CONN_URL, fast_executemany=True, pool_pre_ping=True)


@pytest.fixture(scope="session")
def db_conn(engine):
    with engine.connect() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Database assertions
# ---------------------------------------------------------------------------

class TestDatabase:
    def test_procurement_records_populated(self, db_conn):
        """ProcurementRecords must have rows (seeded from sample_data.csv)."""
        result = db_conn.execute(text("SELECT COUNT(1) FROM procurement.ProcurementRecords"))
        count = result.fetchone()[0]
        assert count > 0, "ProcurementRecords is empty — run data-seed first."

    def test_vendor_scores_exist(self, db_conn):
        """VendorScores must have rows after ML run."""
        result = db_conn.execute(text("SELECT COUNT(1) FROM ai_output.VendorScores"))
        count = result.fetchone()[0]
        assert count > 0, "VendorScores is empty — trigger ML pipeline first."

    def test_vendor_scores_in_range(self, db_conn):
        """All composite scores must be in [0, 100]."""
        result = db_conn.execute(
            text("SELECT MIN(CompositeScore), MAX(CompositeScore) FROM ai_output.VendorScores")
        )
        mn, mx = result.fetchone()
        assert mn >= 0, f"Minimum score {mn} < 0"
        assert mx <= 100, f"Maximum score {mx} > 100"

    def test_anomaly_flags_exist(self, db_conn):
        """AnomalyFlags must have at least 1 row (sample_data has anomalous POs)."""
        result = db_conn.execute(text("SELECT COUNT(1) FROM ai_output.AnomalyFlags"))
        count = result.fetchone()[0]
        assert count >= 1, "No anomaly flags — expected at least 1 from sample_data.csv."

    def test_consolidation_cluster_has_min_members(self, db_conn):
        """At least one consolidation cluster must have ≥ 2 members."""
        result = db_conn.execute(
            text("SELECT COUNT(1) FROM ai_output.ConsolidationClusters WHERE VendorCount >= 2")
        )
        count = result.fetchone()[0]
        assert count >= 1, "No consolidation cluster with ≥ 2 members found."

    def test_performance_band_values(self, db_conn):
        """PerformanceBand column must only contain valid values."""
        result = db_conn.execute(
            text(
                "SELECT DISTINCT PerformanceBand FROM ai_output.VendorScores "
                "WHERE PerformanceBand NOT IN ('GREEN','AMBER','RED','INSUFFICIENT_DATA')"
            )
        )
        invalid = result.fetchall()
        assert len(invalid) == 0, f"Invalid PerformanceBand values: {invalid}"


# ---------------------------------------------------------------------------
# API assertions
# ---------------------------------------------------------------------------

class TestAPI:
    def test_vendor_scores_endpoint(self):
        """GET /vendor-scores returns 200 with non-empty Items."""
        resp = requests.get(f"{API_BASE}/vendor-scores", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "Items" in data
        assert data["TotalCount"] > 0

    def test_anomalies_endpoint(self):
        """GET /anomalies returns at least 1 result."""
        resp = requests.get(f"{API_BASE}/anomalies", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["TotalCount"] >= 1

    def test_consolidation_endpoint(self):
        """GET /consolidation returns data."""
        resp = requests.get(f"{API_BASE}/consolidation", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "Items" in data

    def test_admin_config_endpoint(self):
        """GET /admin/config returns saving_pct_weight field."""
        resp = requests.get(f"{API_BASE}/admin/config", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "saving_pct_weight" in str(data).lower() or "savingPctWeight" in str(data)

    def test_admin_health_endpoint(self):
        """GET /admin/health returns 200."""
        resp = requests.get(f"{API_BASE}/admin/health", timeout=10)
        assert resp.status_code == 200

    def test_swagger_accessible(self):
        """Swagger UI is accessible."""
        api_host = API_BASE.replace("/api/v1", "")
        resp = requests.get(f"{api_host}/swagger/index.html", timeout=10)
        assert resp.status_code == 200

    def test_vendor_scores_pagination(self):
        """Pagination metadata is returned correctly."""
        resp = requests.get(f"{API_BASE}/vendor-scores?page=1&pageSize=5", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["Page"] == 1
        assert data["PageSize"] == 5
        assert len(data["Items"]) <= 5

    def test_anomalies_by_severity(self):
        """GET /anomalies/by-severity/HIGH returns only HIGH severity."""
        resp = requests.get(f"{API_BASE}/anomalies/by-severity/HIGH", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        if data["TotalCount"] > 0:
            for item in data["Items"]:
                assert item["Severity"] == "HIGH"

    def test_ml_trigger(self):
        """POST /admin/ml/trigger returns 202 Accepted."""
        resp = requests.post(
            f"{API_BASE}/admin/ml/trigger",
            json={"runType": "FULL"},
            timeout=15,
        )
        assert resp.status_code in (200, 202, 409), f"Unexpected status {resp.status_code}"


# ---------------------------------------------------------------------------
# ML Engine direct
# ---------------------------------------------------------------------------

class TestMLEngine:
    def test_ml_health(self):
        """ML engine health endpoint responds."""
        resp = requests.get(f"{ML_BASE}/health", timeout=5)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
