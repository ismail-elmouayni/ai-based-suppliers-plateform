# Power BI Setup Guide

## Why Power BI Isn't Running in Docker

Microsoft does not publish an official Docker image for Power BI Report Server.
Power BI Report Server requires a Windows Server GUI installation and cannot run
in a Linux container. See: https://docs.microsoft.com/en-us/power-bi/report-server/

**Solution used in this platform:** Apache Superset (fully Docker-native, Linux)
provides equivalent dashboards at http://localhost:8088

---

## Using the .pbix Placeholder Files

The `.pbix` files in this directory contain pre-built data models connecting to the
same SQL Server views used by the API. To use them:

### Prerequisites

1. **Power BI Desktop** (free): https://powerbi.microsoft.com/desktop/
2. **ODBC Driver 18 for SQL Server**: https://docs.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server
3. SQL Server must be accessible from your Windows machine

### Connection Setup

1. Open a `.pbix` file in Power BI Desktop
2. Click **Transform Data → Data Source Settings**
3. Update the server to `localhost,1433` (or your SQL Server host)
4. Enter credentials: username `sa`, password from your `.env` file
5. Click **Refresh**

### Available Reports

| File | Views Used | Description |
|------|-----------|-------------|
| `VendorRanking.pbix` | `ai_output.VendorScoresLatest` | Top vendors by composite score, band distribution |
| `VendorConsolidation.pbix` | `ai_output.ConsolidationLatestFlat` | Cluster treemap, spend at stake, saving estimates |
| `AnomalyDetection.pbix` | `ai_output.AnomalyFlagsLatest` | Flagged POs, severity breakdown, reason strings |

### Publishing to Power BI Service

1. In Power BI Desktop: **File → Publish → Publish to Power BI**
2. Select a workspace
3. Set up a **Gateway** to keep the SQL Server connection live
4. Schedule refresh as needed (recommended: daily after ML pipeline run)

---

## Superset vs Power BI Feature Comparison

| Feature | Apache Superset | Power BI |
|---------|----------------|----------|
| Docker-native | ✅ | ❌ (Windows only) |
| Free/open source | ✅ | Freemium |
| SQL-based datasets | ✅ | ✅ |
| Interactive filters | ✅ | ✅ |
| Scheduled refresh | ✅ | ✅ (with Gateway) |
| Mobile app | ❌ | ✅ |
| DAX expressions | ❌ | ✅ |
