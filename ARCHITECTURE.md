# Architecture — AI-Powered Supplier Intelligence Platform

## Overview

A fully containerized procurement analytics platform with three AI capabilities:
Vendor Ranking, Vendor Consolidation, and Anomaly Detection.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Network: supplier-net              │
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │SQL Server│◄───│  ML Engine   │    │   .NET 8 REST API    │   │
│  │  :1433   │    │  Flask :5001 │    │       :8080          │   │
│  └──────────┘    └──────────────┘    └──────────────────────┘   │
│       ▲                 ▲                      ▲                 │
│       │                 │                      │                 │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │db-migrate│    │  data-seed   │    │  Apache Superset     │   │
│  │(one-shot)│    │  (one-shot)  │    │      :8088           │   │
│  └──────────┘    └──────────────┘    └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Service Topology

| Service | Image | Port | Role |
|---------|-------|------|------|
| `sqlserver` | `mcr.microsoft.com/mssql/server:2022-latest` | 1433 | Persistent data store |
| `db-migrate` | `data-seed` (migrate stage) | — | One-shot: apply V001–V004 SQL migrations |
| `data-seed` | `data-seed` (seed stage) | — | One-shot: seed ProcurementRecords (profile:seed) |
| `ml-engine` | `ml-engine` (production) | 5001 | Python ML pipeline + Flask trigger server |
| `api` | `api` (.NET 8) | 8080 | REST API + Swagger UI |
| `superset` | `reports` (Superset) | 8088 | Business dashboards |
| `test` | `ml-engine` (test) | — | pytest unit + integration tests (profile:test) |

## Database Schema

### Schemas
- **`procurement`** — raw ingested data and entity resolution
- **`ai_output`** — ML output tables (scores, clusters, anomalies)
- **`ml_admin`** — pipeline run audit log

### Key Tables
```
procurement.ProcurementRecords  ── 1,734 rows from data.xlsx
procurement.ResolvedVendors     ── fuzzy vendor name → canonical mapping
ml_admin.MlRunLog               ── pipeline run history
ai_output.VendorScores          ── composite vendor+category scores
ai_output.ConsolidationClusters ── vendor grouping clusters
ai_output.ConsolidationMembers  ── cluster membership
ai_output.AnomalyFlags          ── flagged POs
```

### Views (latest-run convenience)
- `ai_output.VendorScoresLatest`
- `ai_output.AnomalyFlagsLatest`
- `ai_output.ConsolidationLatestFlat`

## ML Pipeline Execution Order

```
1. Load raw procurement records
        ↓
2. Entity Resolution (rapidfuzz WRatio, threshold=85)
   Writes: procurement.ResolvedVendors
        ↓
3. Attach canonical vendor names to raw data
        ↓
4. Vendor Scoring (min-max normalised, weighted composite)
   Writes: ai_output.VendorScores
        ↓
5. Consolidation Clustering (KMeans auto-k elbow)
   Writes: ai_output.ConsolidationClusters + ConsolidationMembers
        ↓
6. Anomaly Detection (IsolationForest + Z-score)
   Writes: ai_output.AnomalyFlags
        ↓
7. Update ml_admin.MlRunLog (COMPLETED)
```

## Configuration Hot-Reload

`ml-engine/config/model_config.yml` is mounted read-only into both
`ml-engine` and `api` containers. Changing any weight value takes effect
on the **next ML pipeline run** — no redeployment required.

## API Design

- Base path: `/api/v1/`
- Pagination: `PagedResult<T>` with `Items`, `TotalCount`, `Page`, `PageSize`,
  `TotalPages`, `HasNextPage`, `HasPreviousPage`
- Error format: `{ type, message, detail, timestamp, traceId }`
- Swagger UI: `http://localhost:8080/swagger`

## Power BI Blocker

Microsoft does not publish an official Docker image for Power BI Report Server
(requires Windows Server GUI). Solution: Apache Superset (fully Docker-native,
Linux) provides equivalent dashboards. `.pbix` placeholder files + setup guide
are in `reports/pbix/POWERBI_SETUP_GUIDE.md`.
