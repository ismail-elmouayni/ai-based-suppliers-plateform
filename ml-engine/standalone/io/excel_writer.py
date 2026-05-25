"""
ExcelWriter
===========
Writes all pipeline results to a single ``output.xlsx`` workbook using
``xlsxwriter`` for rich formatting and embedded charts.

Sheet layout
------------
1. **Summary**               — KPI tiles + spend-by-category bar chart
2. **Entity_Resolution**     — vendor name mapping table
3. **Vendor_Scores**         — scored vendor table + horizontal bar chart
4. **Consolidation_Clusters**— cluster summaries + savings bar chart
5. **Consolidation_Members** — vendor membership per cluster
6. **Anomaly_Flags**         — flagged POs + severity pie chart

Usage
-----
::

    with ExcelWriter("output.xlsx") as w:
        w.write_summary(stats, raw_df)
        w.write_entity_resolution(mapping_df)
        w.write_vendor_scores(scores_df)
        w.write_consolidation(clusters_df, members_df)
        w.write_anomaly_flags(flags_df)
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Union

import pandas as pd

from anomaly_detection.anomaly_flag import AnomalyFlag, Severity
from consolidation.cluster_result import ClusterMember, ConsolidationCluster
from entity_resolution.vendor_mapping import VendorMapping
from vendor_scoring.vendor_score import VendorScore
import xlsxwriter
from xlsxwriter.workbook import Workbook
from xlsxwriter.worksheet import Worksheet

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

COLOUR = {
    "header_bg": "#1F3864",   # dark navy
    "header_fg": "#FFFFFF",
    "green_bg": "#C6EFCE",
    "green_fg": "#276221",
    "amber_bg": "#FFEB9C",
    "amber_fg": "#9C6500",
    "red_bg": "#FFC7CE",
    "red_fg": "#9C0006",
    "grey_bg": "#D9D9D9",
    "grey_fg": "#595959",
    "kpi_bg": "#EBF3FB",
    "alt_row": "#F2F7FB",
}

BAND_COLOURS = {
    "GREEN":            (COLOUR["green_bg"], COLOUR["green_fg"]),
    "AMBER":            (COLOUR["amber_bg"], COLOUR["amber_fg"]),
    "RED":              (COLOUR["red_bg"],   COLOUR["red_fg"]),
    "INSUFFICIENT_DATA":(COLOUR["grey_bg"],  COLOUR["grey_fg"]),
}

SEVERITY_COLOURS = {
    "HIGH":   (COLOUR["red_bg"],   COLOUR["red_fg"]),
    "MEDIUM": (COLOUR["amber_bg"], COLOUR["amber_fg"]),
    "LOW":    (COLOUR["green_bg"], COLOUR["green_fg"]),
}

# Chart colours matching the performance bands
CHART_BAND_COLOURS = {
    "GREEN": "#70AD47",
    "AMBER": "#FFC000",
    "RED":   "#FF0000",
}

# ---------------------------------------------------------------------------
# ExcelWriter
# ---------------------------------------------------------------------------

class ExcelWriter:
    """Context-manager that writes pipeline results to a single workbook.

    Parameters
    ----------
    path:
        Destination path for the ``.xlsx`` file.
    """

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)
        self._wb: Workbook | None = None
        self._fmt: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "ExcelWriter":
        self._wb = xlsxwriter.Workbook(str(self.path))
        self._wb.set_properties({"title": "Supplier Intelligence Report"})
        self._build_formats()
        return self

    def __exit__(self, *_: Any) -> None:
        if self._wb:
            self._wb.close()
        logger.info("Output workbook written to '%s'.", self.path)

    # ------------------------------------------------------------------
    # Public write methods
    # ------------------------------------------------------------------

    def write_summary(self, stats: dict[str, Any], raw_df: pd.DataFrame) -> None:
        """Write the Summary sheet with KPI tiles and a spend-by-category chart."""
        ws = self._wb.add_worksheet("Summary")
        ws.set_zoom(90)
        ws.hide_gridlines(2)
        ws.set_column("A:A", 3)
        ws.set_column("B:E", 22)

        # ── Title ──────────────────────────────────────────────────────
        ws.merge_range("B2:E2", "Supplier Intelligence — Pipeline Report", self._fmt["title"])
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        ws.merge_range("B3:E3", f"Generated: {ts}", self._fmt["subtitle"])

        # ── KPI tiles ──────────────────────────────────────────────────
        kpis = [
            ("Total Vendors",     stats.get("total_vendors", 0),    "B"),
            ("Total Spend",       f"${stats.get('total_spend', 0):,.0f}", "C"),
            ("Anomalies Flagged", stats.get("anomaly_count", 0),    "D"),
            ("Consolidation Clusters", stats.get("cluster_count", 0), "E"),
        ]
        for label, value, col in kpis:
            ws.merge_range(f"{col}5:{col}6", label,  self._fmt["kpi_label"])
            ws.merge_range(f"{col}7:{col}8", value,  self._fmt["kpi_value"])

        # ── Spend by category table (used as chart source) ─────────────
        if not raw_df.empty and "Category" in raw_df.columns:
            spend_by_cat = (
                raw_df.dropna(subset=["Category"])
                .groupby("Category")["Spend"]
                .sum()
                .sort_values(ascending=False)
                .reset_index()
            )
            table_row = 10
            ws.write(table_row, 1, "Category",      self._fmt["col_header"])
            ws.write(table_row, 2, "Total Spend",   self._fmt["col_header"])
            for i, (_, row) in enumerate(spend_by_cat.iterrows()):
                r = table_row + 1 + i
                fmt = self._fmt["alt_row"] if i % 2 else self._fmt["cell"]
                ws.write(r, 1, row["Category"], fmt)
                ws.write(r, 2, row["Spend"],    self._fmt["money"])

            # Bar chart
            chart = self._wb.add_chart({"type": "bar"})
            data_rows = len(spend_by_cat)
            chart.add_series({
                "name":       "Total Spend",
                "categories": ["Summary", table_row + 1, 1, table_row + data_rows, 1],
                "values":     ["Summary", table_row + 1, 2, table_row + data_rows, 2],
                "fill":       {"color": "#2E75B6"},
                "gap":        80,
            })
            chart.set_title({"name": "Total Spend by Category"})
            chart.set_x_axis({"num_format": "$#,##0"})
            chart.set_legend({"none": True})
            chart.set_size({"width": 480, "height": 300})
            ws.insert_chart("B" + str(table_row + data_rows + 3), chart)

    def write_entity_resolution(self, mappings: list[VendorMapping]) -> None:
        """Write the Entity_Resolution sheet."""
        ws = self._wb.add_worksheet("Entity_Resolution")
        ws.set_zoom(90)
        ws.freeze_panes(1, 0)

        columns = [
            ("RawVendorName",     30),
            ("CanonicalVendorName", 30),
            ("MatchScore",         14),
            ("MatchMethod",        18),
        ]
        mapping_df = pd.DataFrame([
            {
                "RawVendorName":      m.raw_vendor_name,
                "CanonicalVendorName": m.canonical_vendor_name,
                "MatchScore":         m.match_score,
                "MatchMethod":        m.match_method,
            }
            for m in mappings
        ])
        self._write_table(ws, mapping_df, columns)

    def write_vendor_scores(self, scores: list[VendorScore]) -> None:
        """Write the Vendor_Scores sheet with a horizontal bar chart."""
        ws = self._wb.add_worksheet("Vendor_Scores")
        ws.set_zoom(90)
        ws.freeze_panes(1, 0)

        columns = [
            ("CanonicalVendorName",      30),
            ("Category",                 20),
            ("CompositeScore",           16),
            ("PerformanceBand",          18),
            ("SavingPctNorm",            16),
            ("SpendNorm",                14),
            ("SpecializationNorm",       18),
            ("RawAverageSavingPercent",  22),
            ("RawTotalSpend",            16),
            ("RawSpecialization",        18),
            ("RawPurchaseCount",         14),
        ]

        df = pd.DataFrame([
            {
                "CanonicalVendorName":     s.canonical_vendor_name,
                "Category":                s.category,
                "CompositeScore":          s.composite_score,
                "PerformanceBand":         s.performance_band,
                "SavingPctNorm":           s.saving_pct_norm,
                "SpendNorm":               s.spend_norm,
                "SpecializationNorm":      s.specialization_norm,
                "RawAverageSavingPercent": s.raw_average_saving_percent,
                "RawTotalSpend":           s.raw_total_spend,
                "RawSpecialization":       s.raw_specialization,
                "RawPurchaseCount":        s.raw_purchase_count,
            }
            for s in scores
        ]).sort_values("CompositeScore", ascending=False).reset_index(drop=True)
        self._write_table(ws, df, columns, band_col="PerformanceBand")

        # ── Horizontal bar chart (top 20 by score) ────────────────────
        chart_df = df[df["PerformanceBand"] != "INSUFFICIENT_DATA"].head(20)
        if not chart_df.empty:
            self._write_vendor_score_chart(ws, chart_df, start_row=len(df) + 3)

    def write_consolidation(
        self, clusters: list[ConsolidationCluster], members: list[ClusterMember]
    ) -> None:
        """Write Consolidation_Clusters and Consolidation_Members sheets."""
        # ── Clusters ──────────────────────────────────────────────────
        ws_c = self._wb.add_worksheet("Consolidation_Clusters")
        ws_c.set_zoom(90)
        ws_c.freeze_panes(1, 0)

        cluster_cols = [
            ("ClusterLabel",          14),
            ("DominantCategory",      22),
            ("VendorCount",           14),
            ("TotalSpendAtStake",     20),
            ("EstimatedSavingPct",    20),
            ("EstimatedSavingAmount", 22),
        ]
        clusters_df = pd.DataFrame([
            {
                "ClusterLabel":          c.cluster_label,
                "DominantCategory":      c.dominant_category,
                "VendorCount":           c.vendor_count,
                "TotalSpendAtStake":     c.total_spend_at_stake,
                "EstimatedSavingPct":    c.estimated_saving_pct,
                "EstimatedSavingAmount": c.estimated_saving_amount,
            }
            for c in clusters
        ])
        self._write_table(ws_c, clusters_df, cluster_cols)

        # Bar chart: estimated savings per cluster
        if clusters:
            self._write_savings_chart(ws_c, clusters, start_row=len(clusters) + 3)

        # ── Members ───────────────────────────────────────────────────
        ws_m = self._wb.add_worksheet("Consolidation_Members")
        ws_m.set_zoom(90)
        ws_m.freeze_panes(1, 0)

        member_cols = [
            ("ClusterLabel",       14),
            ("CanonicalVendorName", 30),
            ("VendorTotalSpend",    18),
            ("CategoriesSupplied",  40),
        ]
        members_df = pd.DataFrame([
            {
                "ClusterLabel":        m.cluster_label,
                "CanonicalVendorName": m.canonical_vendor_name,
                "VendorTotalSpend":    m.vendor_total_spend,
                "CategoriesSupplied":  m.categories_supplied,
            }
            for m in members
        ])
        self._write_table(ws_m, members_df, member_cols)

    def write_anomaly_flags(self, flags: list[AnomalyFlag]) -> None:
        """Write the Anomaly_Flags sheet with a severity pie chart."""
        ws = self._wb.add_worksheet("Anomaly_Flags")
        ws.set_zoom(90)
        ws.freeze_panes(1, 0)

        columns = [
            ("PO_Number",          14),
            ("CanonicalVendorName", 28),
            ("Category",           18),
            ("Original_Spend",     16),
            ("Spend",              14),
            ("SpendGap",           14),
            ("AnomalyScore",       14),
            ("ZScore",             12),
            ("Severity",           12),
            ("ReasonString",       50),
        ]

        flags_df = pd.DataFrame([
            {
                "PO_Number":          f.po_number,
                "CanonicalVendorName": f.canonical_vendor_name,
                "Category":           f.category,
                "Original_Spend":     f.original_spend,
                "Spend":              f.spend,
                "SpendGap":           f.spend_gap,
                "AnomalyScore":       f.anomaly_score,
                "ZScore":             f.z_score,
                "Severity":           f.severity,
                "ReasonString":       f.reason_string,
            }
            for f in flags
        ])
        self._write_table(ws, flags_df, columns, severity_col="Severity")

        if not flags_df.empty:
            self._write_severity_pie_chart(ws, flags_df, start_row=len(flags_df) + 3)

    # ------------------------------------------------------------------
    # Shared table writer
    # ------------------------------------------------------------------

    def _write_table(
        self,
        ws: Worksheet,
        df: pd.DataFrame,
        columns: list[tuple[str, int]],
        band_col: str | None = None,
        severity_col: str | None = None,
    ) -> None:
        """Write a DataFrame to *ws* starting at row 0.

        Parameters
        ----------
        columns:
            List of ``(column_name, column_width)`` pairs.  Only the columns
            listed here are written; extra columns in *df* are ignored.
        band_col:
            Name of the ``PerformanceBand`` column — cells receive band colours.
        severity_col:
            Name of the ``Severity`` column — cells receive severity colours.
        """
        col_names = [c[0] for c in columns]
        col_widths = [c[1] for c in columns]

        # Header row
        for j, (name, width) in enumerate(zip(col_names, col_widths)):
            ws.write(0, j, name, self._fmt["col_header"])
            ws.set_column(j, j, width)

        if df.empty:
            return

        # Data rows
        for i, (_, row) in enumerate(df.iterrows()):
            base_fmt = self._fmt["alt_row"] if i % 2 else self._fmt["cell"]
            for j, col in enumerate(col_names):
                value = row.get(col, "")
                if pd.isna(value):
                    value = ""

                # Choose cell format
                if col == band_col:
                    band = str(value)
                    bg, fg = BAND_COLOURS.get(band, (COLOUR["grey_bg"], COLOUR["grey_fg"]))
                    fmt = self._wb.add_format({
                        "bg_color": bg, "font_color": fg,
                        "bold": True, "align": "center",
                        "border": 1, "border_color": "#BFBFBF",
                    })
                elif col == severity_col:
                    sev = str(value)
                    bg, fg = SEVERITY_COLOURS.get(sev, (COLOUR["grey_bg"], COLOUR["grey_fg"]))
                    fmt = self._wb.add_format({
                        "bg_color": bg, "font_color": fg,
                        "bold": True, "align": "center",
                        "border": 1, "border_color": "#BFBFBF",
                    })
                elif isinstance(value, float) and col in (
                    "CompositeScore", "AnomalyScore", "ZScore",
                    "RawSavingPct", "RawSpecialization", "EstimatedSavingPct",
                ):
                    fmt = self._fmt["pct_2dp"]
                elif isinstance(value, (int, float)) and col in (
                    "RawTotalSpend", "Spend", "Original_Spend",
                    "SpendGap", "TotalSpendAtStake", "EstimatedSavingAmount",
                    "VendorTotalSpend",
                ):
                    fmt = self._fmt["money"]
                else:
                    fmt = base_fmt

                ws.write(i + 1, j, value, fmt)

    # ------------------------------------------------------------------
    # Chart builders
    # ------------------------------------------------------------------

    def _write_vendor_score_chart(
        self, ws: Worksheet, chart_df: pd.DataFrame, start_row: int
    ) -> None:
        """Embed a horizontal bar chart of the top-20 vendor scores."""
        # Write chart data to a hidden area below the main table
        data_start = start_row
        ws.write(data_start,     0, "Vendor+Category",  self._fmt["col_header"])
        ws.write(data_start,     1, "Score",            self._fmt["col_header"])
        ws.write(data_start,     2, "Band",             self._fmt["col_header"])

        for i, (_, row) in enumerate(chart_df.iterrows()):
            label = f"{row['CanonicalVendorName']} / {row['Category']}"
            ws.write(data_start + 1 + i, 0, label,                  self._fmt["cell"])
            ws.write(data_start + 1 + i, 1, row["CompositeScore"],   self._fmt["pct_2dp"])
            ws.write(data_start + 1 + i, 2, row["PerformanceBand"],  self._fmt["cell"])

        n = len(chart_df)

        # One series per band so each bar can be individually coloured
        chart = self._wb.add_chart({"type": "bar"})
        for band, colour in CHART_BAND_COLOURS.items():
            band_rows = [
                (data_start + 1 + i, row)
                for i, (_, row) in enumerate(chart_df.iterrows())
                if row["PerformanceBand"] == band
            ]
            if not band_rows:
                continue
            # We must write individual points — xlsxwriter bar charts support
            # per-point colours via a single series with point overrides.

        # Simpler approach: single series + per-point colour overrides
        points = []
        for _, row in chart_df.iterrows():
            colour = CHART_BAND_COLOURS.get(row["PerformanceBand"], "#7F7F7F")
            points.append({"fill": {"color": colour}})

        chart.add_series({
            "name":       "Composite Score",
            "categories": [ws.name, data_start + 1, 0, data_start + n, 0],
            "values":     [ws.name, data_start + 1, 1, data_start + n, 1],
            "points":     points,
            "gap":        60,
        })
        chart.set_title({"name": "Vendor Performance Scores (Top 20)"})
        chart.set_x_axis({"min": 0, "max": 100, "name": "Composite Score"})
        chart.set_y_axis({"name": "Vendor / Category"})
        chart.set_legend({"none": True})
        chart.set_size({"width": 640, "height": max(300, 25 * n)})
        ws.insert_chart(data_start + n + 3, 0, chart)

    def _write_savings_chart(
        self, ws: Worksheet, clusters: list[ConsolidationCluster], start_row: int
    ) -> None:
        """Embed a bar chart of estimated savings per cluster."""
        data_start = start_row
        ws.write(data_start,     0, "Cluster",          self._fmt["col_header"])
        ws.write(data_start,     1, "Est. Saving ($)",  self._fmt["col_header"])

        for i, c in enumerate(clusters):
            label = f"Cluster {c.cluster_label} — {c.dominant_category}"
            ws.write(data_start + 1 + i, 0, label,                       self._fmt["cell"])
            ws.write(data_start + 1 + i, 1, c.estimated_saving_amount,   self._fmt["money"])

        n = len(clusters)
        chart = self._wb.add_chart({"type": "column"})
        chart.add_series({
            "name":       "Estimated Saving",
            "categories": [ws.name, data_start + 1, 0, data_start + n, 0],
            "values":     [ws.name, data_start + 1, 1, data_start + n, 1],
            "fill":       {"color": "#70AD47"},
            "gap":        80,
        })
        chart.set_title({"name": "Estimated Savings by Consolidation Cluster"})
        chart.set_y_axis({"num_format": "$#,##0", "name": "Estimated Saving ($)"})
        chart.set_legend({"none": True})
        chart.set_size({"width": 540, "height": 300})
        ws.insert_chart(data_start + n + 3, 0, chart)

    def _write_severity_pie_chart(
        self, ws: Worksheet, flags_df: pd.DataFrame, start_row: int
    ) -> None:
        """Embed a pie chart showing anomaly counts by severity."""
        severity_counts = flags_df["Severity"].value_counts().reset_index()
        severity_counts.columns = ["Severity", "Count"]

        data_start = start_row
        ws.write(data_start, 0, "Severity", self._fmt["col_header"])
        ws.write(data_start, 1, "Count",    self._fmt["col_header"])

        sev_colours = {"HIGH": "#FF0000", "MEDIUM": "#FFC000", "LOW": "#70AD47"}
        points = []
        for i, (_, row) in enumerate(severity_counts.iterrows()):
            ws.write(data_start + 1 + i, 0, row["Severity"], self._fmt["cell"])
            ws.write(data_start + 1 + i, 1, int(row["Count"]), self._fmt["cell"])
            points.append({"fill": {"color": sev_colours.get(row["Severity"], "#7F7F7F")}})

        n = len(severity_counts)
        chart = self._wb.add_chart({"type": "pie"})
        chart.add_series({
            "name":       "Anomaly Severity",
            "categories": [ws.name, data_start + 1, 0, data_start + n, 0],
            "values":     [ws.name, data_start + 1, 1, data_start + n, 1],
            "points":     points,
            "data_labels": {"percentage": True, "category": True},
        })
        chart.set_title({"name": "Anomaly Flags by Severity"})
        chart.set_size({"width": 400, "height": 300})
        ws.insert_chart(data_start + n + 3, 0, chart)

    # ------------------------------------------------------------------
    # Format registry
    # ------------------------------------------------------------------

    def _build_formats(self) -> None:
        """Pre-register all reusable cell formats."""
        wb = self._wb

        self._fmt["title"] = wb.add_format({
            "bold": True, "font_size": 16,
            "bg_color": COLOUR["header_bg"], "font_color": COLOUR["header_fg"],
            "align": "center", "valign": "vcenter",
        })
        self._fmt["subtitle"] = wb.add_format({
            "italic": True, "font_size": 10,
            "bg_color": COLOUR["header_bg"], "font_color": "#B4C6E7",
            "align": "center",
        })
        self._fmt["kpi_label"] = wb.add_format({
            "bold": True, "font_size": 10,
            "bg_color": COLOUR["kpi_bg"], "align": "center", "valign": "vcenter",
            "border": 1, "border_color": "#BDD7EE",
        })
        self._fmt["kpi_value"] = wb.add_format({
            "bold": True, "font_size": 18,
            "bg_color": COLOUR["kpi_bg"], "font_color": "#1F3864",
            "align": "center", "valign": "vcenter",
            "border": 1, "border_color": "#BDD7EE",
        })
        self._fmt["col_header"] = wb.add_format({
            "bold": True,
            "bg_color": COLOUR["header_bg"], "font_color": COLOUR["header_fg"],
            "border": 1, "border_color": "#FFFFFF",
            "align": "center", "valign": "vcenter", "text_wrap": True,
        })
        self._fmt["cell"] = wb.add_format({
            "border": 1, "border_color": "#BFBFBF", "valign": "vcenter",
        })
        self._fmt["alt_row"] = wb.add_format({
            "bg_color": COLOUR["alt_row"],
            "border": 1, "border_color": "#BFBFBF", "valign": "vcenter",
        })
        self._fmt["money"] = wb.add_format({
            "num_format": "$#,##0.00",
            "border": 1, "border_color": "#BFBFBF",
        })
        self._fmt["pct_2dp"] = wb.add_format({
            "num_format": "0.00",
            "border": 1, "border_color": "#BFBFBF",
        })
