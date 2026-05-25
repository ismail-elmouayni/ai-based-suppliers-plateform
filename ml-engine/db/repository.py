"""
DataRepository — SQLAlchemy-based data access layer for the ML engine.

Handles:
  - Loading raw procurement data
  - Writing resolved vendors, vendor scores, consolidation clusters/members, anomaly flags
  - MlRunLog lifecycle management
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from anomaly_detection.anomaly_flag import AnomalyFlag
from vendor_scoring.vendor_score import VendorScore
from data_source_columns import DataSourceColumns

logger = logging.getLogger(__name__)


def _build_connection_url() -> str:
    host = os.getenv("MSSQL_HOST", "sqlserver")
    port = os.getenv("MSSQL_PORT", "1433")
    db = os.getenv("MSSQL_DATABASE", "SupplierIntelligence")
    user = os.getenv("MSSQL_USER", "sa")
    password = os.getenv("MSSQL_SA_PASSWORD", "")
    driver = "ODBC+Driver+18+for+SQL+Server"
    return (
        f"mssql+pyodbc://{user}:{password}@{host}:{port}/{db}"
        f"?driver={driver}&TrustServerCertificate=yes&Encrypt=yes"
    )


class DataRepository:
    def __init__(self, engine: Optional[Engine] = None):
        self._engine = engine or create_engine(
            _build_connection_url(),
            fast_executemany=True,
            pool_pre_ping=True,
        )

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    @contextmanager
    def _conn(self):
        with self._engine.connect() as conn:
            yield conn

    # ------------------------------------------------------------------
    # MlRunLog
    # ------------------------------------------------------------------

    def create_run_log(
        self,
        run_type: str,
        triggered_by: str = "SYSTEM",
        config_snapshot: Optional[Dict] = None,
    ) -> int:
        """Insert a PENDING run log entry and return the new Id."""
        snapshot = json.dumps(config_snapshot) if config_snapshot else None
        with self._conn() as conn:
            result = conn.execute(
                text(
                    "INSERT INTO ml_admin.MlRunLog (RunType, TriggeredBy, Status, ConfigSnapshot) "
                    "OUTPUT INSERTED.Id "
                    "VALUES (:run_type, :triggered_by, 'PENDING', :config_snapshot)"
                ),
                {"run_type": run_type, "triggered_by": triggered_by, "config_snapshot": snapshot},
            )
            run_id = result.fetchone()[0]
            conn.commit()
        logger.info(f"Created MlRunLog entry Id={run_id} (RunType={run_type})")
        return run_id

    def update_run_log_running(self, run_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                text(
                    "UPDATE ml_admin.MlRunLog SET Status='RUNNING', StartedAt=SYSUTCDATETIME() "
                    "WHERE Id=:id"
                ),
                {"id": run_id},
            )
            conn.commit()

    def update_run_log_completed(self, run_id: int, duration_ms: int) -> None:
        with self._conn() as conn:
            conn.execute(
                text(
                    "UPDATE ml_admin.MlRunLog "
                    "SET Status='COMPLETED', CompletedAt=SYSUTCDATETIME(), DurationMs=:ms "
                    "WHERE Id=:id"
                ),
                {"ms": duration_ms, "id": run_id},
            )
            conn.commit()

    def update_run_log_failed(self, run_id: int, error_message: str) -> None:
        with self._conn() as conn:
            conn.execute(
                text(
                    "UPDATE ml_admin.MlRunLog "
                    "SET Status='FAILED', CompletedAt=SYSUTCDATETIME(), ErrorMessage=:err "
                    "WHERE Id=:id"
                ),
                {"err": error_message[:4000], "id": run_id},
            )
            conn.commit()

    def get_latest_run_log(self) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute(
                text(
                    "SELECT TOP 1 Id, RunType, Status, StartedAt, CompletedAt, DurationMs, ErrorMessage "
                    "FROM ml_admin.MlRunLog ORDER BY StartedAt DESC"
                )
            ).fetchone()
        if row is None:
            return None
        return dict(row._mapping)

    # ------------------------------------------------------------------
    # Load raw data
    # ------------------------------------------------------------------

    def load_procurement_records(self) -> pd.DataFrame:
        """Load all procurement records."""
        with self._conn() as conn:
            df = pd.read_sql(
                "SELECT Id, Country, Vendor, Category, PO_Number, Item_Description, "
                "Original_Spend, OPEX_CAPEX, Saving, Saving_Pct, Spend "
                "FROM procurement.ProcurementRecords",
                conn,
            )
        logger.info(f"Loaded {len(df)} procurement records.")
        return df

    def load_resolved_vendors(self, run_id: int) -> pd.DataFrame:
        """Load the vendor name mapping for a specific run."""
        with self._conn() as conn:
            df = pd.read_sql(
                "SELECT RawVendorName, CanonicalVendorName "
                "FROM procurement.ResolvedVendors "
                "WHERE ResolutionRunId = :run_id",
                conn,
                params={"run_id": run_id},
            )
        return df

    # ------------------------------------------------------------------
    # Write entity resolution
    # ------------------------------------------------------------------

    def write_resolved_vendors(self, mapping_df: pd.DataFrame) -> None:
        """Bulk insert vendor name mapping into procurement.ResolvedVendors."""
        if mapping_df.empty:
            return

        # Delete previous mapping for same run
        run_ids = mapping_df["ResolutionRunId"].dropna().unique().tolist()
        if run_ids:
            with self._conn() as conn:
                conn.execute(
                    text("DELETE FROM procurement.ResolvedVendors WHERE ResolutionRunId = :rid"),
                    {"rid": int(run_ids[0])},
                )
                conn.commit()

        mapping_df.to_sql(
            "ResolvedVendors",
            self._engine,
            schema="procurement",
            if_exists="append",
            index=False,
            chunksize=500,
        )
        logger.info(f"Wrote {len(mapping_df)} resolved vendor mappings.")

    # ------------------------------------------------------------------
    # Write vendor scores
    # ------------------------------------------------------------------

    def write_vendor_scores(self, scores: list[VendorScore]) -> None:
        if not scores:
            return
        rows = [
            {
                "RunId":                          s.run_id,
                DataSourceColumns.CANONICAL_VENDOR: s.canonical_vendor_name,
                DataSourceColumns.CATEGORY:         s.category,
                "CompositeScore":                 s.composite_score,
                "PerformanceBand":                s.performance_band,
                "SavingPctNorm":                  s.saving_pct_norm,
                "SpendNorm":                      s.spend_norm,
                "SpecializationNorm":             s.specialization_norm,
                "RawAverageSavingPercent":        s.raw_average_saving_percent,
                "RawTotalSpend":                  s.raw_total_spend,
                "RawSpecialization":              s.raw_specialization,
                "RawPurchaseCount":               s.raw_purchase_count,
            }
            for s in scores
        ]
        pd.DataFrame(rows).to_sql(
            "VendorScores",
            self._engine,
            schema="ai_output",
            if_exists="append",
            index=False,
            chunksize=500,
        )
        logger.info(f"Wrote {len(scores)} vendor score rows.")

    # ------------------------------------------------------------------
    # Write consolidation results
    # ------------------------------------------------------------------

    def write_consolidation(
        self, clusters_df: pd.DataFrame, members_df: pd.DataFrame
    ) -> None:
        if clusters_df.empty:
            return

        # Insert clusters and capture generated Ids
        with self._engine.begin() as conn:
            for _, row in clusters_df.iterrows():
                result = conn.execute(
                    text(
                        "INSERT INTO ai_output.ConsolidationClusters "
                        "(RunId, ClusterLabel, DominantCategory, VendorCount, "
                        "TotalSpendAtStake, EstimatedSavingPct, EstimatedSavingAmount) "
                        "OUTPUT INSERTED.Id "
                        "VALUES (:run_id, :label, :dom_cat, :vendor_count, "
                        ":total_spend, :saving_pct, :saving_amt)"
                    ),
                    {
                        "run_id": int(row["RunId"]),
                        "label": int(row["ClusterLabel"]),
                        "dom_cat": row.get("DominantCategory"),
                        "vendor_count": int(row["VendorCount"]),
                        "total_spend": float(row["TotalSpendAtStake"]),
                        "saving_pct": float(row.get("EstimatedSavingPct") or 0),
                        "saving_amt": float(row.get("EstimatedSavingAmount") or 0),
                    },
                )
                cluster_id = result.fetchone()[0]

                # Insert members for this cluster
                cluster_members = members_df[
                    members_df["ClusterLabel"] == row["ClusterLabel"]
                ]
                for _, m in cluster_members.iterrows():
                    conn.execute(
                        text(
                            "INSERT INTO ai_output.ConsolidationMembers "
                            "(ClusterId, CanonicalVendorName, VendorTotalSpend, CategoriesSupplied) "
                            "VALUES (:cid, :vendor, :spend, :cats)"
                        ),
                        {
                            "cid": cluster_id,
                            "vendor": m["CanonicalVendorName"],
                            "spend": float(m.get("VendorTotalSpend") or 0),
                            "cats": str(m.get("CategoriesSupplied") or ""),
                        },
                    )

        logger.info(
            f"Wrote {len(clusters_df)} consolidation clusters and "
            f"{len(members_df)} members."
        )

    # ------------------------------------------------------------------
    # Write anomaly flags
    # ------------------------------------------------------------------

    def write_anomaly_flags(self, flags: list[AnomalyFlag]) -> None:
        if not flags:
            return

        rows = [
            {
                "RunId":               f.run_id,
                "SourceRecordId":      f.source_record_id,
                "PO_Number":           f.po_number,
                "CanonicalVendorName": f.canonical_vendor_name,
                "Category":            f.category,
                "Original_Spend":      f.original_spend,
                "Spend":               f.spend,
                "SpendGap":            f.spend_gap,
                "AnomalyScore":        f.anomaly_score,
                "ZScore":              f.z_score,
                "Severity":            f.severity,
                "ReasonString":        f.reason_string,
            }
            for f in flags
        ]
        pd.DataFrame(rows).to_sql(
            "AnomalyFlags",
            self._engine,
            schema="ai_output",
            if_exists="append",
            index=False,
            chunksize=500,
        )
        logger.info(f"Wrote {len(flags)} anomaly flags.")
