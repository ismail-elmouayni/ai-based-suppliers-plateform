# AI-Powered Supplier Intelligence Platform

A production-ready, fully containerized procurement analytics platform with three AI capabilities:
**Vendor Ranking**, **Vendor Consolidation**, and **Anomaly Detection**.

## Quick Start

```bash
# 1. Copy environment file and set your SQL Server password
cp .env.example .env

# 2. Start all services
docker compose up -d --build

# 3. Apply database migrations (runs automatically, or manually:)
docker compose run db-migrate

# 4. Seed with real data (1,734 rows from data.xlsx)
docker compose --profile seed up data-seed

# 5. Trigger the ML pipeline
curl -X POST http://localhost:5001/run
# or via the API:
curl -X POST http://localhost:8080/api/v1/admin/ml/trigger \
  -H "Content-Type: application/json" -d '{"runType":"FULL"}'

# 6. Explore results
open http://localhost:8080/swagger    # REST API + Swagger UI
open http://localhost:8088            # Superset dashboards (admin / Admin1234!)
```

## Services

| Service | URL | Credentials |
|---------|-----|-------------|
| REST API + Swagger | http://localhost:8080/swagger | — |
| Apache Superset | http://localhost:8088 | admin / Admin1234! |
| ML Engine health | http://localhost:5001/health | — |
| SQL Server | localhost:1433 | sa / (from .env) |

## API Endpoints (base: `/api/v1/`)

### Vendor Ranking
```
GET  /vendor-scores                          All vendor scores (paginated)
GET  /vendor-scores/by-category/{category}  Scores for a category
GET  /vendor-scores/by-vendor/{vendorName}  Scores for a vendor
GET  /vendor-scores/by-band/{band}          GREEN / AMBER / RED / INSUFFICIENT_DATA
```

### Consolidation
```
GET  /consolidation                          All clusters (paginated)
GET  /consolidation/{clusterId}             Single cluster with members
GET  /consolidation/by-category/{category}
GET  /consolidation/by-vendor/{vendorName}
```

### Anomaly Detection
```
GET  /anomalies                              All flags (paginated)
GET  /anomalies/by-severity/{severity}      HIGH / MEDIUM / LOW
GET  /anomalies/by-vendor/{vendorName}
GET  /anomalies/by-category/{category}
GET  /anomalies/{id}                        Single anomaly detail
```

### Admin
```
POST /admin/ml/trigger                       Trigger full ML pipeline
GET  /admin/ml/status                        Latest run status
GET  /admin/ml/runs                          Run history (paginated)
GET  /admin/config                           Current model config
GET  /admin/health                           API health check
```

## Running Tests

```bash
# All tests (integration + unit):
docker compose --profile test run test

# Unit tests only (no DB required):
docker compose run --no-deps ml-engine pytest vendor_scoring/tests/ -v
docker compose run --no-deps ml-engine pytest entity_resolution/tests/ -v
docker compose run --no-deps ml-engine pytest anomaly_detection/tests/ -v
docker compose run --no-deps ml-engine pytest consolidation/tests/ -v
```

## Configuration

Edit `ml-engine/config/model_config.yml` to adjust ML parameters.
Changes take effect on the **next ML run** — no redeployment needed.

Key parameters:
- `saving_pct_weight` — weight for savings performance (default: 0.50)
- `spend_weight` — weight for total spend volume (default: 0.30)
- `specialization_weight` — weight for category focus (default: 0.20)
- `contamination_factor` — proportion of POs flagged as anomalies (default: 0.05)
- `match_threshold` — fuzzy match minimum score for vendor consolidation (default: 85)

## Verification Checklist

After `docker compose up`:

1. `docker compose run db-migrate` → migrations applied
2. `docker compose --profile seed up data-seed` → 1,734 rows seeded
3. `curl -X POST http://localhost:5001/run` → ML pipeline runs
4. `curl http://localhost:8080/api/v1/vendor-scores` → scores returned
5. `curl http://localhost:8080/api/v1/anomalies` → flagged POs returned
6. `curl http://localhost:8080/swagger` → OpenAPI UI accessible
7. http://localhost:8088 → Superset dashboards visible
8. `docker compose --profile test run test` → all tests pass

## Power BI

Microsoft does not provide a Docker image for Power BI Report Server (Windows Server
only). Placeholder `.pbix` files and a setup guide are in `reports/pbix/`.
See `reports/pbix/POWERBI_SETUP_GUIDE.md` for connecting Power BI Desktop to
the SQL Server views.

## Project Structure

```
├── docker-compose.yml
├── .env.example
├── data.xlsx                    (1,734 real procurement rows)
├── db/migrations/               (V001–V004 SQL scripts)
├── data-seed/                   (seed utility + sample CSV)
├── ml-engine/                   (Python ML pipeline + Flask :5001)
│   ├── entity_resolution/
│   ├── vendor_scoring/
│   ├── consolidation/
│   ├── anomaly_detection/
│   └── config/model_config.yml
├── api/                         (.NET 8 REST API)
├── reports/                     (Apache Superset + .pbix)
└── docs/AI_CAPABILITIES_GUIDE.md
```
