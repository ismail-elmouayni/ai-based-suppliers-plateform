# Claude Code Implementation Prompt — AI-Powered Supplier Intelligence Platform

## Context & Mission

You are tasked with implementing a production-ready, fully containerized
**AI-Powered Supplier Intelligence Platform** for a procurement department. The
platform ingests procurement data (purchase orders, vendors, spend figures) from a
SQL Server database and delivers three AI-driven capabilities:

1. **Vendor Ranking** — composite scoring of vendors per spend category (0–100 scale)
2. **Vendor Consolidation** — clustering-based identification of consolidation
   opportunities across vendors supplying equivalent goods within the same category
3. **Anomaly Detection** — statistical detection of abnormal spend deviations on
   purchase orders

Results are exposed via a REST API and visualized in Power BI reports. The entire
platform runs inside Docker containers for both local development and production
deployment, including Power BI report serving.

> **Scope boundary**: implement only the three capabilities listed above. Do not
> implement NLP category classification, RAG/conversational Q&A, savings leakage
> detection, or risk concentration analysis — these are out of scope for this
> iteration.

---

## Domain Knowledge

### Data Model

The procurement database contains the following core fields. Your data layer must
map to this schema exactly:

| Field            | Type    | Description                                     |
|------------------|---------|-------------------------------------------------|
| `Country`        | String  | Procurement country (e.g. Morocco)              |
| `Vendor`         | String  | Supplier name (~244 unique, with inconsistencies)|
| `Category`       | String  | Spend category (~27 types)                      |
| `PO_Number`      | String  | Purchase order identifier                       |
| `Item_Description`| String | Free-text line item description                 |
| `Original_Spend` | Numeric | Initial contracted amount                       |
| `OPEX_CAPEX`     | Enum    | Expenditure type (OPEX / CAPEX)                 |
| `Saving`         | Numeric | Absolute saving achieved                        |
| `Saving_Pct`     | Numeric | Relative saving rate (%)                        |
| `Spend`          | Numeric | Final actual spend                              |

### Known Data Quality Issues

The platform must handle these issues gracefully — do not assume clean data:

- **Vendor name inconsistencies**: the same supplier may appear under slightly
  different names (e.g. `TP GROUP INC` vs `TELEPERFORMANCE GROUP, INC.`). A vendor
  entity resolution step (fuzzy matching / normalization) must run before any
  scoring or clustering.
- **NULL categories**: some records have no category assigned. These records must
  be excluded from category-scoped computations and flagged in the API response.
- **Mixed-language descriptions**: Item_Description may contain French and English
  text — treat these as opaque strings for this scope.

### Feature Specifications

#### 1 — Vendor Ranking

- Compute a **composite score between 0 and 100** for each vendor, scoped per
  category. A vendor active in 3 categories will have 3 independent scores.
- The score must combine at minimum: savings performance (`Saving_Pct`), spend
  volume (`Spend`), and category specialization index (ratio of vendor's spend in
  this category vs. its total spend across all categories).
- Assign a **performance band** to each score: `GREEN` (≥ 70), `AMBER` (40–69),
  `RED` (< 40).
- Scoring weights (e.g. weight of `Saving_Pct` vs. spend volume) must be
  **externalized in a configuration file** so they can be adjusted without
  redeploying. Document the config schema clearly.
- The model must support **retraining / recalibration** when new data is loaded.
  Expose a trigger endpoint for this.

#### 2 — Vendor Consolidation

- Build a **vendor × category spend matrix** from the resolved vendor data.
- Apply **clustering** to identify groups of vendors that supply the same or
  overlapping categories with similar spend profiles.
- For each identified cluster (consolidation opportunity), compute and expose:
  - List of vendors in the cluster
  - Dominant category
  - Total spend at stake
  - Estimated saving potential (derive a reasonable heuristic based on average
    Saving_Pct in that category vs. the best-performing vendor in the cluster)
- Output must be consumable by Power BI (flat table or set of related tables).

#### 3 — Anomaly Detection

- Detect purchase orders where the **gap between `Original_Spend` and `Spend`**
  is statistically abnormal given the vendor and category context.
- Use an **unsupervised approach** — no labelled anomaly data is available.
- Each flagged PO must carry: an anomaly score, a severity label (`LOW` /
  `MEDIUM` / `HIGH`), and a human-readable reason string explaining why it was
  flagged (e.g. "Spend exceeds original by 3.2σ above category mean").
- The detection sensitivity must be tunable via the same configuration file used
  for vendor scoring.

---

## Architecture Guidance

### Language & Technology Preferences

- **C#** is preferred for the API layer, orchestration, data access, and any
  service coordination logic.
- **Python** is preferred for all ML/AI processing: scoring models, clustering,
  anomaly detection, and data preparation pipelines.
- For everything else (databases, messaging, containerization, report serving),
  **you decide** the most appropriate tool. Justify your choices briefly in a
  `ARCHITECTURE.md` file at the root of the repository.
- Do **not** use any external AI API (no OpenAI, no Azure OpenAI, no cloud
  inference endpoints). All model inference runs locally inside containers.

### Layered Architecture Expectations

Design the system in clearly separated layers. At minimum:

- **Data Integration Layer**: responsible for reading from SQL Server, running
  entity resolution on vendor names, and producing a clean, AI-ready dataset.
- **AI Processing Layer**: Python services/scripts that consume the clean dataset
  and produce scored results, consolidation clusters, and anomaly flags. Results
  are written back to dedicated output tables in the database.
- **API Layer**: C# REST API that exposes the AI outputs to consumers (Power BI,
  future integrations). This layer never re-runs ML inference — it reads from
  output tables only.
- **Presentation Layer**: Power BI reports served inside Docker for local testing,
  reading from the API or directly from output tables.

The layers must be independently deployable containers. Define all inter-layer
contracts (API schemas, database table structures, config file formats) explicitly
in the codebase.

### Data Residency Constraint

All processing is strictly on-premise / within the container network. No data
must leave the Docker network boundary during inference or reporting. Validate
this in your architecture decisions.

---

## Containerization Requirements

### General Rules

- The entire platform — SQL Server, Python ML services, C# API, Power BI report
  server, and any supporting infrastructure — must be runnable with a **single
  `docker compose up`** command for local development.
- Each service must have its own `Dockerfile`. Use multi-stage builds where
  appropriate to keep images lean.
- All environment-specific configuration (database connection strings, ports,
  feature flags) must be managed through **environment variables** with sane
  defaults for local development, documented in a root-level `.env.example` file.
- The compose file must define explicit **health checks** for each service, and
  dependent services must wait for their dependencies to be healthy before
  starting.

### Power BI Container

- Include a container that serves the Power BI reports for local testing purposes.
  Use **Power BI Report Server** (or the most appropriate self-hostable image
  available) as the basis for this container.
- Pre-load the three report files (Vendor Ranking, Anomaly Detection, Vendor
  Consolidation) into the report server on startup.
- Document in `README.md` how to access the reports locally (URL, default
  credentials).
- If Power BI Report Server cannot be fully automated via Docker in a reasonable
  way, provide a clearly documented fallback (e.g. `.pbix` files with a connection
  setup guide), and note the limitation explicitly.

### Database Bootstrapping Utility

- Provide a **dedicated utility container** (or a CLI tool invokable via
  `docker compose run`) that can:
  1. Initialize the SQL Server schema (create all required tables, indexes, and
     output views) from migration scripts.
  2. Seed the database from a **CSV file** that mimics an ERP export (matching the
     schema in the Domain Knowledge section above). The CSV path must be
     configurable via environment variable.
- This utility is the primary way to set up a local test environment. It must be
  idempotent (safe to run multiple times).
- Include a realistic **sample CSV file** with at least 50 synthetic rows covering
  multiple vendors, categories, and edge cases (NULL category, vendor name
  variants, anomalous spend gaps).

---

## Repository Structure

Organize the repository so that each major component is a top-level directory.
Suggested (adapt as you see fit, and justify deviations in `ARCHITECTURE.md`):

```
/
├── docker-compose.yml
├── .env.example
├── ARCHITECTURE.md
├── README.md
│
├── db/
│   └── migrations/          # SQL scripts for schema initialization
│
├── data-seed/
│   ├── Dockerfile
│   ├── seed.py (or equivalent)
│   └── sample_data.csv
│
├── ml-engine/               # Python ML processing layer
│   ├── Dockerfile
│   ├── vendor_scoring/
│   ├── consolidation/
│   ├── anomaly_detection/
│   └── config/
│       └── model_config.yml # Scoring weights, detection sensitivity
│
├── api/                     # C# REST API
│   ├── Dockerfile
│   └── ...
│
└── reports/                 # Power BI report files and server config
    ├── Dockerfile
    ├── VendorRanking.pbix
    ├── AnomalyDetection.pbix
    └── VendorConsolidation.pbix
```

---

## API Contract Requirements

The C# API must expose at minimum the following endpoints. You decide the exact
URL scheme, versioning strategy, and response envelope format — document it.

| Capability           | Required Operations                                                              |
|----------------------|----------------------------------------------------------------------------------|
| Vendor Ranking       | Get all scores; get scores by category; get scores by vendor; filter by band    |
| Vendor Consolidation | Get all consolidation opportunities; get by category; get by vendor              |
| Anomaly Detection    | Get all flagged POs; filter by severity; filter by vendor; filter by category    |
| Administration       | Trigger ML recomputation; get last run timestamp and status; get config summary  |

- All list endpoints must support **pagination**.
- All filter parameters must be documented via **OpenAPI / Swagger** (auto-generated
  from code, not hand-written).
- The API must return structured errors with a consistent error schema.

---

## Configuration File

The scoring weights and anomaly detection sensitivity are the primary tunable
parameters. They must live in a single YAML configuration file (e.g.
`model_config.yml`) mounted into the ML container. Provide a well-commented
default version. At minimum it must control:

- Relative weight of `Saving_Pct`, `Spend` volume, and category specialization in
  the vendor composite score
- Minimum number of POs required for a vendor-category pair to be scored
  (below this threshold, the pair is marked `INSUFFICIENT_DATA`)
- Anomaly detection sensitivity (contamination factor or equivalent parameter
  controlling the proportion of POs expected to be anomalous)
- Minimum cluster size for consolidation opportunities to be reported

---

## Testing Requirements

- Provide **unit tests** for the scoring formula, the anomaly flagging logic, and
  the entity resolution step. Use the sample CSV data as test fixtures.
- Provide at least one **integration test** that spins up the database, seeds it
  with sample data, runs the ML pipeline, and asserts that the API returns
  non-empty ranked results and at least one anomaly flag.
- Tests must be runnable inside Docker (`docker compose run test` or equivalent).

---

## Documentation Requirements

Deliver the following documentation alongside the code:

- **`README.md`** — quickstart guide: prerequisites, how to run locally with
  `docker compose up`, how to seed the database, how to access the API and Power
  BI reports, how to tune the config file.
- **`ARCHITECTURE.md`** — architecture decision log: why you chose specific tools,
  how the layers interact, data flow diagram (ASCII or Mermaid), and any
  assumptions made about the production environment.
- **Inline code comments** on all non-obvious logic, especially in the ML engine
  (scoring formula, clustering parameters, anomaly threshold derivation).
- **OpenAPI spec** auto-generated and accessible at `/swagger` on the API service.

---

## Execution Instructions for Claude Code

1. **Start in plan mode.** Before writing any code, produce a complete
   `ARCHITECTURE.md` describing your technology choices, layer design, data flow,
   and container topology. Wait for approval (or proceed if running unattended).

2. **Implement in this order**:
   - Database schema migrations and the seeding utility with sample CSV
   - ML engine: entity resolution → vendor scoring → consolidation → anomaly
     detection
   - C# REST API reading from output tables
   - Docker Compose wiring of all services
   - Power BI report files and report server container
   - Tests and documentation

3. **Validate at each step**: after implementing each layer, verify it works in
   isolation before wiring it to the next layer.

4. **Do not shortcut the configuration file**: the `model_config.yml` must be
   genuinely functional — changing a weight value must change scoring outcomes.

5. **Flag blockers explicitly**: if a specific requirement (e.g. Power BI Report
   Server Docker image availability) cannot be fully implemented as described,
   document the blocker clearly and implement the best available alternative
   rather than silently skipping it.
