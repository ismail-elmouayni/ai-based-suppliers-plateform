#!/usr/bin/env python3
"""
Generate a Superset 3.x compatible import ZIP — no external dependencies.

Usage:
    python reports/generate_superset_import.py

Produces: supplier_intelligence_import.zip (in current directory)
Import:   Superset UI → Dashboards → ↑ Import → select the ZIP
          When prompted about the database connection, tick Overwrite.
"""

import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, List, Optional

OUTPUT = "supplier_intelligence_import.zip"
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
EXPORT_DIR = f"dashboard_export_{TIMESTAMP}"

# ── Stable UUIDs ──────────────────────────────────────────────────────────────
DB_UUID         = "a0000001-0000-0000-0000-000000000001"
DS_VENDOR_UUID  = "a0000002-0000-0000-0000-000000000001"
DS_ANOMALY_UUID = "a0000002-0000-0000-0000-000000000002"
DS_CONSOL_UUID  = "a0000002-0000-0000-0000-000000000003"
CH_VENDOR_UUID  = "a0000003-0000-0000-0000-000000000001"
CH_BAND_UUID    = "a0000003-0000-0000-0000-000000000002"
CH_ANOMALY_UUID = "a0000003-0000-0000-0000-000000000003"
CH_CONSOL_UUID  = "a0000003-0000-0000-0000-000000000004"
DASH_UUID       = "a0000004-0000-0000-0000-000000000001"

DB_NAME      = "Supplier Intelligence SQL Server"
DB_NAME_SAFE = "Supplier_Intelligence_SQL_Server"


# ── Minimal YAML serialiser (no pyyaml needed) ────────────────────────────────

_NEEDS_QUOTE_STARTS = set(':?|>!%@`&*{[#,\'"\\-')
_NEEDS_QUOTE_WORDS  = {'true', 'false', 'null', 'yes', 'no', 'on', 'off', ''}

def _inline(v: Any) -> Optional[str]:
    """Return inline YAML string for simple scalars / empty containers, else None."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        if (v.lower() in _NEEDS_QUOTE_WORDS
                or (v and v[0] in _NEEDS_QUOTE_STARTS)
                or ':' in v or '#' in v or '\n' in v):
            return "'" + v.replace("'", "''") + "'"
        return v
    if isinstance(v, list) and not v:
        return "[]"
    if isinstance(v, dict) and not v:
        return "{}"
    return None  # needs block form


def _emit(obj: Any, depth: int, out: List[str]) -> None:
    pad = "  " * depth
    if isinstance(obj, dict):
        for k, v in obj.items():
            iv = _inline(v)
            if iv is not None:
                out.append(f"{pad}{k}: {iv}")
            elif isinstance(v, list):
                out.append(f"{pad}{k}:")
                for item in v:
                    ii = _inline(item)
                    if ii is not None:
                        out.append(f"{pad}- {ii}")
                    elif isinstance(item, dict):
                        first = True
                        for ik, iv2 in item.items():
                            prefix = f"{pad}- " if first else f"{pad}  "
                            iv2i = _inline(iv2)
                            if iv2i is not None:
                                out.append(f"{prefix}{ik}: {iv2i}")
                            else:
                                out.append(f"{prefix}{ik}:")
                                _emit(iv2, depth + 2, out)
                            first = False
                    else:
                        out.append(f"{pad}-")
                        _emit(item, depth + 1, out)
            elif isinstance(v, dict):
                out.append(f"{pad}{k}:")
                _emit(v, depth + 1, out)
    elif isinstance(obj, list):
        for item in obj:
            ii = _inline(item)
            if ii is not None:
                out.append(f"{pad}- {ii}")
            else:
                _emit(item, depth, out)


def to_yaml(data: dict) -> str:
    out: List[str] = []
    _emit(data, 0, out)
    return "\n".join(out) + "\n"


# ── ZIP helper ────────────────────────────────────────────────────────────────

def zwrite(zf: zipfile.ZipFile, path: str, content: str) -> None:
    zf.writestr(f"{EXPORT_DIR}/{path}", content)


# ── Entity builders ───────────────────────────────────────────────────────────

def make_metadata() -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return {"version": "1.0.0", "type": "Dashboard", "timestamp": ts}


def make_database() -> dict:
    return {
        "database_name": DB_NAME,
        "sqlalchemy_uri": (
            "mssql+pyodbc://sa:SupplierIntelligence2024!@sqlserver:1433"
            "/SupplierIntelligence?driver=ODBC+Driver+18+for+SQL+Server"
            "&TrustServerCertificate=yes&Encrypt=yes"
        ),
        "cache_timeout": None,
        "expose_in_sqllab": True,
        "allow_run_async": False,
        "allow_ctas": False,
        "allow_cvas": False,
        "allow_dml": False,
        "allow_file_upload": False,
        "extra": {
            "metadata_params": {},
            "engine_params": {},
            "schemas_allowed_for_file_upload": [],
            "cost_estimate_enabled": False,
        },
        "uuid": DB_UUID,
        "version": "1.0.0",
    }


def _col(name: str, typ: str, is_dttm: bool = False) -> dict:
    return {
        "column_name": name,
        "verbose_name": None,
        "is_dttm": is_dttm,
        "is_active": True,
        "type": typ,
        "advanced_data_type": None,
        "groupby": True,
        "filterable": True,
        "expression": "",
        "description": None,
        "python_date_format": None,
        "extra": {},
    }


_COUNT = {
    "metric_name": "count",
    "verbose_name": "",
    "metric_type": "count",
    "expression": "COUNT(*)",
    "description": None,
    "d3format": None,
    "extra": {},
    "warning_text": None,
}


def _dataset(table_name, schema, desc, uuid, cols) -> dict:
    return {
        "table_name": table_name,
        "main_dttm_col": None,
        "description": desc,
        "default_endpoint": None,
        "filter_select_enabled": True,
        "offset": 0,
        "cache_timeout": None,
        "schema": schema,
        "sql": None,
        "params": None,
        "template_params": None,
        "fetch_values_predicate": None,
        "extra": None,
        "uuid": uuid,
        "metrics": [_COUNT],
        "columns": cols,
        "database_uuid": DB_UUID,
        "version": "1.0.0",
    }


def make_vendor_scores_ds() -> dict:
    return _dataset("VendorScoresLatest", "ai_output",
        "Latest vendor performance scores from the ML pipeline", DS_VENDOR_UUID, [
        _col("Id",                  "BIGINT"),
        _col("RunId",               "BIGINT"),
        _col("CanonicalVendorName", "NVARCHAR(500)"),
        _col("Category",            "NVARCHAR(200)"),
        _col("CompositeScore",      "DECIMAL(6,2)"),
        _col("PerformanceBand",     "NVARCHAR(20)"),
        _col("SavingPctNorm",       "DECIMAL(8,6)"),
        _col("SpendNorm",           "DECIMAL(8,6)"),
        _col("SpecializationNorm",  "DECIMAL(8,6)"),
        _col("RawSavingPct",        "DECIMAL(10,8)"),
        _col("RawTotalSpend",       "DECIMAL(18,4)"),
        _col("RawSpecialization",   "DECIMAL(8,6)"),
        _col("PurchaseCount",          "INT"),
        _col("CreatedAt",           "DATETIME2", is_dttm=True),
    ])


def make_anomaly_flags_ds() -> dict:
    return _dataset("AnomalyFlagsLatest", "ai_output",
        "Anomaly flags from the latest ML pipeline run", DS_ANOMALY_UUID, [
        _col("Id",                  "BIGINT"),
        _col("RunId",               "BIGINT"),
        _col("SourceRecordId",      "BIGINT"),
        _col("PO_Number",           "NVARCHAR(100)"),
        _col("CanonicalVendorName", "NVARCHAR(500)"),
        _col("Category",            "NVARCHAR(200)"),
        _col("Original_Spend",      "DECIMAL(18,4)"),
        _col("Spend",               "DECIMAL(18,4)"),
        _col("SpendGap",            "DECIMAL(18,4)"),
        _col("AnomalyScore",        "DECIMAL(8,6)"),
        _col("ZScore",              "DECIMAL(10,4)"),
        _col("Severity",            "NVARCHAR(10)"),
        _col("ReasonString",        "NVARCHAR(MAX)"),
        _col("CreatedAt",           "DATETIME2", is_dttm=True),
    ])


def make_consolidation_ds() -> dict:
    return _dataset("ConsolidationLatestFlat", "ai_output",
        "Consolidation opportunities from the latest ML pipeline run", DS_CONSOL_UUID, [
        _col("ClusterId",             "BIGINT"),
        _col("RunId",                 "BIGINT"),
        _col("ClusterLabel",          "INT"),
        _col("DominantCategory",      "NVARCHAR(200)"),
        _col("VendorCount",           "INT"),
        _col("TotalSpendAtStake",     "DECIMAL(18,4)"),
        _col("EstimatedSavingPct",    "DECIMAL(8,6)"),
        _col("EstimatedSavingAmount", "DECIMAL(18,4)"),
        _col("MemberId",              "BIGINT"),
        _col("CanonicalVendorName",   "NVARCHAR(500)"),
        _col("VendorTotalSpend",      "DECIMAL(18,4)"),
        _col("CategoriesSupplied",    "NVARCHAR(MAX)"),
    ])


def _chart(name, viz_type, params, ds_uuid, uuid) -> dict:
    return {
        "slice_name": name,
        "viz_type": viz_type,
        "params": json.dumps(params),
        "query_context": "",
        "cache_timeout": None,
        "certified_by": None,
        "certification_details": None,
        "description": None,
        "uuid": uuid,
        "version": "1.0.0",
        "dataset_uuid": ds_uuid,
    }


def make_vendor_table_chart() -> dict:
    return _chart("Vendor Scores", "table", {
        "adhoc_filters": [],
        "all_columns": ["CanonicalVendorName", "Category", "CompositeScore",
                        "PerformanceBand", "PurchaseCount", "RawSavingPct", "RawTotalSpend"],
        "order_desc": True, "row_limit": 200,
        "time_range": "No filter", "include_search": True, "show_cell_bars": False,
    }, DS_VENDOR_UUID, CH_VENDOR_UUID)


def make_band_pie_chart() -> dict:
    return _chart("Performance Band Distribution", "pie", {
        "adhoc_filters": [], "color_scheme": "supersetColors",
        "donut": False, "groupby": ["PerformanceBand"],
        "innerRadius": 30, "label_type": "key_value", "labels_outside": True,
        "metric": {"aggregate": "COUNT",
                   "column": {"column_name": "Id", "type": "BIGINT"},
                   "expressionType": "SIMPLE", "label": "COUNT(Id)",
                   "optionName": "metric_count"},
        "outerRadius": 70, "row_limit": 100,
        "show_labels": True, "show_legend": True, "time_range": "No filter",
    }, DS_VENDOR_UUID, CH_BAND_UUID)


def make_anomaly_table_chart() -> dict:
    return _chart("Anomaly Flags", "table", {
        "adhoc_filters": [],
        "all_columns": ["PO_Number", "CanonicalVendorName", "Category", "Severity",
                        "Original_Spend", "Spend", "SpendGap",
                        "AnomalyScore", "ZScore", "ReasonString"],
        "order_desc": True, "row_limit": 500,
        "time_range": "No filter", "include_search": True, "show_cell_bars": False,
    }, DS_ANOMALY_UUID, CH_ANOMALY_UUID)


def make_consolidation_table_chart() -> dict:
    return _chart("Consolidation Opportunities", "table", {
        "adhoc_filters": [],
        "all_columns": ["DominantCategory", "VendorCount", "TotalSpendAtStake",
                        "EstimatedSavingPct", "EstimatedSavingAmount",
                        "CanonicalVendorName", "VendorTotalSpend", "CategoriesSupplied"],
        "order_desc": True, "row_limit": 500,
        "time_range": "No filter", "include_search": True, "show_cell_bars": False,
    }, DS_CONSOL_UUID, CH_CONSOL_UUID)


def _chart_node(node_id, chart_uuid, name, w, h) -> dict:
    return {"children": [], "id": node_id,
            "meta": {"chartId": 0, "height": h, "sliceName": name,
                     "uuid": chart_uuid, "width": w},
            "type": "CHART"}


def make_dashboard() -> dict:
    return {
        "dashboard_title": "Supplier Intelligence Platform",
        "description": "AI-powered procurement analytics",
        "css": "",
        "slug": None,
        "uuid": DASH_UUID,
        "position": {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID":  {"children": ["GRID_ID"], "id": "ROOT_ID", "type": "ROOT"},
            "GRID_ID":  {"children": ["ROW-vendor", "ROW-anomaly", "ROW-consol"],
                         "id": "GRID_ID", "type": "GRID"},
            "ROW-vendor":  {"children": ["CHART-vendor", "CHART-band"],
                            "id": "ROW-vendor",
                            "meta": {"background": "BACKGROUND_TRANSPARENT"},
                            "type": "ROW"},
            "ROW-anomaly": {"children": ["CHART-anomaly"],
                            "id": "ROW-anomaly",
                            "meta": {"background": "BACKGROUND_TRANSPARENT"},
                            "type": "ROW"},
            "ROW-consol":  {"children": ["CHART-consol"],
                            "id": "ROW-consol",
                            "meta": {"background": "BACKGROUND_TRANSPARENT"},
                            "type": "ROW"},
            "CHART-vendor":  _chart_node("CHART-vendor",  CH_VENDOR_UUID,  "Vendor Scores", 8, 60),
            "CHART-band":    _chart_node("CHART-band",    CH_BAND_UUID,    "Performance Band Distribution", 4, 60),
            "CHART-anomaly": _chart_node("CHART-anomaly", CH_ANOMALY_UUID, "Anomaly Flags", 12, 60),
            "CHART-consol":  _chart_node("CHART-consol",  CH_CONSOL_UUID,  "Consolidation Opportunities", 12, 60),
        },
        "metadata": {
            "color_scheme": "supersetColors",
            "refresh_frequency": 0,
            "timed_refresh_immune_slices": [],
            "expanded_slices": {},
            "default_filters": "{}",
            "chart_configuration": {},
            "native_filter_configuration": [],
        },
        "certified_by": None,
        "certification_details": None,
        "published": True,
        "version": "1.0.0",
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zwrite(zf, "metadata.yaml",                                       to_yaml(make_metadata()))
        zwrite(zf, f"databases/{DB_NAME_SAFE}.yaml",                      to_yaml(make_database()))
        zwrite(zf, f"datasets/{DB_NAME_SAFE}/VendorScoresLatest.yaml",    to_yaml(make_vendor_scores_ds()))
        zwrite(zf, f"datasets/{DB_NAME_SAFE}/AnomalyFlagsLatest.yaml",    to_yaml(make_anomaly_flags_ds()))
        zwrite(zf, f"datasets/{DB_NAME_SAFE}/ConsolidationLatestFlat.yaml", to_yaml(make_consolidation_ds()))
        zwrite(zf, "charts/Vendor_Scores.yaml",                           to_yaml(make_vendor_table_chart()))
        zwrite(zf, "charts/Performance_Band_Distribution.yaml",           to_yaml(make_band_pie_chart()))
        zwrite(zf, "charts/Anomaly_Flags.yaml",                           to_yaml(make_anomaly_table_chart()))
        zwrite(zf, "charts/Consolidation_Opportunities.yaml",             to_yaml(make_consolidation_table_chart()))
        zwrite(zf, "dashboards/Supplier_Intelligence_Platform.yaml",      to_yaml(make_dashboard()))

    with open(OUTPUT, "wb") as f:
        f.write(buf.getvalue())

    print(f"Generated: {OUTPUT}")
    print("Import: Superset UI → Dashboards → ↑ Import → select the ZIP → tick Overwrite → Import")


if __name__ == "__main__":
    main()
