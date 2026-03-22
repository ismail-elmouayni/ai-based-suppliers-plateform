# Apache Superset — User Guide
### AI-Powered Supplier Intelligence Platform

This guide is written for business users — no technical knowledge required.
It covers how to open Superset, navigate its interface, import the ready-made
dashboards and charts, and use them day-to-day.

---

## 1. What is Superset?

Apache Superset is the **reporting and dashboards** layer of this platform.
It connects directly to the SQL Server database and lets you explore the AI
outputs through visual charts and tables — without writing any code or SQL.

Three areas of analysis are available:

| Area | What you see |
|---|---|
| **Vendor Ranking** | Composite score (0–100) and GREEN / AMBER / RED band for each supplier |
| **Anomaly Detection** | Purchase orders where the final amount differed significantly from the agreed price |
| **Consolidation** | Groups of suppliers delivering similar goods, with estimated savings from consolidating |

---

## 2. How to open Superset

Open your browser and go to:

```
http://localhost:8088
```

Log in with:
- **Username:** `admin`
- **Password:** `Admin1234!`

You will land on the Superset home page.

---

## 3. Navigating the interface

The top navigation bar has four main sections:

| Menu item | What it contains |
|---|---|
| **Dashboards** | Pre-built pages combining multiple charts in one view |
| **Charts** | Individual charts and tables you can explore or edit |
| **Datasets** | The database views that feed the charts |
| **Settings** | Database connections, users, and security |

---

## 4. Importing the ready-made dashboard

A complete dashboard file is provided at:

```
reports/superset/supplier_intelligence_import.zip
```

This single ZIP file contains everything: the database connection, the three
datasets, the four charts, and the dashboard layout.

**Steps to import:**

1. In Superset, click **Dashboards** in the top navigation bar.
2. Click the **↑ Import** button at the top right of the page.
3. Click **Select file** and choose:
   ```
   reports/superset/supplier_intelligence_import.zip
   ```
4. A summary screen appears listing what will be imported.
   - Tick the **Overwrite** checkbox next to the database connection row
     (this ensures the connection is registered even if one exists already).
5. Click **Import**.
6. A green confirmation message appears. Click **Dashboards** again —
   you will see **Supplier Intelligence Platform** in the list.
7. Click its title to open it.

> **If the import fails:** See Section 9 — Troubleshooting.

---

## 5. Importing individual charts or datasets

If you only need to import specific charts or datasets (for example, to add
them to a dashboard you built yourself), individual export files are provided:

### Datasets (the data sources)

| File | What it contains |
|---|---|
| `reports/superset/dataset/dataset_export_*` (first file) | `VendorScoresLatest` — vendor performance scores |
| `reports/superset/dataset/dataset_export_*` (second file) | `AnomalyFlagsLatest` — flagged purchase orders |
| `reports/superset/dataset/dataset_export_*` (third file) | `ConsolidationLatestFlat` — consolidation clusters |

To import a dataset:
1. Click **Datasets** in the top navigation bar.
2. Click the **↑ Import** button (top right).
3. Select the ZIP file and click **Import**.

### Charts

| File | What it contains |
|---|---|
| `reports/superset/charts/chart_export_*` (file 1) | Vendor Scores table |
| `reports/superset/charts/chart_export_*` (file 2) | Performance Band Distribution pie chart |
| `reports/superset/charts/chart_export_*` (file 3) | Anomaly Flags table |
| `reports/superset/charts/chart_export_*` (file 4) | Consolidation Opportunities table |

To import a chart:
1. Click **Charts** in the top navigation bar.
2. Click the **↑ Import** button (top right).
3. Select the ZIP file and click **Import**.

---

## 6. Using the Supplier Intelligence Dashboard

Once imported, open the dashboard by clicking its title in the Dashboards list.

### What you see

The dashboard is divided into three rows:

**Row 1 — Vendor Ranking**
- Left panel: a table listing all vendors with their composite score,
  performance band, PO count, saving percentage, and spend volume.
- Right panel: a pie chart showing how many vendors fall into each band
  (GREEN, AMBER, RED, INSUFFICIENT DATA).

**Row 2 — Anomaly Detection**
- A table of flagged purchase orders, showing the PO number, vendor, category,
  severity, original amount, final amount, the gap between them, and a
  plain-language explanation of why it was flagged.

**Row 3 — Consolidation Opportunities**
- A table of supplier clusters, showing the dominant category, number of
  vendors in the cluster, total spend at stake, and estimated saving amount.

### Filtering

Each table has a **search bar** at the top right — type any text to filter rows
instantly. For example, type `HIGH` in the Anomaly Flags table to show only
high-severity anomalies, or type a supplier name to find all records for that
supplier.

### Refreshing after a new ML run

The charts read from the database views, which always show the **latest
completed ML pipeline run**. After triggering a new run:

1. Wait for the pipeline to finish (check
   `http://localhost:8080/api/v1/admin/ml/status`).
2. On the dashboard, click the **⋯ (three dots)** menu at the top right of
   any chart.
3. Click **Force refresh**.
4. Repeat for each chart, or use the dashboard-level **↻ Refresh** button
   at the top right of the page.

---

## 7. Exploring data in SQL Lab

SQL Lab lets you write your own queries against the database — useful if you
want to answer a specific question not covered by the dashboards.

1. Click **SQL Lab** → **SQL Editor** in the top navigation bar.
2. Select **Supplier Intelligence SQL Server** from the database dropdown.
3. Select **ai_output** from the schema dropdown.
4. Write a query, for example:
   ```sql
   SELECT TOP 10
       CanonicalVendorName,
       CompositeScore,
       PerformanceBand
   FROM ai_output.VendorScoresLatest
   ORDER BY CompositeScore DESC
   ```
5. Click **Run** (or press `Ctrl + Enter`).

The three views available are:

| View | Description |
|---|---|
| `ai_output.VendorScoresLatest` | Vendor scores from the latest ML run |
| `ai_output.AnomalyFlagsLatest` | Anomaly flags from the latest ML run |
| `ai_output.ConsolidationLatestFlat` | Consolidation clusters and their members |

---

## 8. Adding the database connection manually

If the database connection was not registered automatically during import, add
it yourself:

1. Click **Settings** (top right) → **Database Connections**.
2. Click **+ Database**.
3. Select **Microsoft SQL Server** from the list.
4. In the **SQLAlchemy URI** field, paste exactly:
   ```
   mssql+pyodbc://sa:SupplierIntelligence2024!@sqlserver:1433/SupplierIntelligence?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=yes
   ```
5. Click **Test Connection** — it should say "Connection looks good!"
6. Click **Connect**.

---

## 9. Troubleshooting

### "Error importing dashboard — please re-export your file"
- Make sure you are selecting the correct ZIP file (`supplier_intelligence_import.zip`).
- Do not unzip the file before importing — Superset expects the ZIP as-is.
- Tick **Overwrite** on the database connection row before clicking Import.

### Dashboard shows "No results" or empty charts
- The ML pipeline has not been run yet, or the last run failed.
- Trigger a run: `POST http://localhost:8080/api/v1/admin/ml/trigger`
  (or use the Swagger UI at `http://localhost:8080/swagger`).
- Check the run status at `http://localhost:8080/api/v1/admin/ml/status`.

### Superset is not accessible at localhost:8088
- The container may still be starting. Wait 2–3 minutes after
  `docker compose up` and try again.
- Check container status with `docker compose ps`.

### Charts show stale data after a new ML run
- Use **Force refresh** on each chart (⋯ menu → Force refresh), or
  click the dashboard-level **↻** button at the top right.

---

## 10. File reference

| File | Purpose |
|---|---|
| `reports/superset/supplier_intelligence_import.zip` | **Full import** — database + datasets + charts + dashboard in one file |
| `reports/superset/dataset/dataset_export_*.zip` | Individual dataset exports |
| `reports/superset/charts/chart_export_*.zip` | Individual chart exports |
| `reports/superset/dashboard/dashboard_export_*.zip` | Dashboard-only export (requires datasets and charts to be imported first) |
| `reports/generate_superset_import.py` | Script that regenerates `supplier_intelligence_import.zip` from scratch |
