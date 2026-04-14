# Standalone Supplier Intelligence Pipeline

A self-contained CLI tool that runs the full AI pipeline — entity resolution,
vendor scoring, consolidation clustering, and anomaly detection — using a local
Excel file as input and producing a richly formatted Excel report as output.

No database or network connection is required.

---

## Prerequisites

- Python 3.9 or later
- pip 21+ (upgrade if needed: `python -m pip install --upgrade pip`)

---

## Installation

From the `ml-engine` folder (the workspace root):

```bash
pip install -r standalone/requirements.txt
```

---

## Input file — `data.xlsx`

Place your procurement data in a file named `data.xlsx` in the workspace root
(or anywhere you like — see the `--input` option below).

The file must contain one sheet with the following columns.
Both underscore and space-separated names are accepted (e.g. `PO_Number` or
`PO Number`, `Saving_Pct` or `Saving %`).

| Column | Type | Notes |
|---|---|---|
| `Id` | integer | Optional — auto-generated if absent |
| `Country` | string | |
| `Vendor` | string | Raw vendor name (before resolution) |
| `Category` | string | Product / service category |
| `PO_Number` | string | Purchase order identifier |
| `Item_Description` | string | |
| `Original_Spend` | number | Budget / initial quote |
| `OPEX_CAPEX` | string | `OPEX` or `CAPEX` |
| `Saving` | number | Absolute saving amount |
| `Saving_Pct` | number | Saving as a ratio, e.g. `0.15` = 15% (also accepted: `Saving %`) |
| `Spend` | number | Final spend amount |

The sheet can be named anything; the reader looks for a sheet called
`ProcurementRecords` first and falls back to the first sheet.

---

## Running the pipeline

### Basic usage

```bash
python standalone/main.py
```

This reads `data.xlsx` and writes `output.xlsx`, both in the workspace root,
using `config/model_config.yml` for algorithm parameters.

### Full options

```bash
python standalone/main.py \
  --input  path/to/data.xlsx \
  --output path/to/output.xlsx \
  --config path/to/model_config.yml
```

| Flag | Short | Default | Description |
|---|---|---|---|
| `--input` | `-i` | `data.xlsx` | Path to the input Excel file |
| `--output` | `-o` | `output.xlsx` | Path for the generated report |
| `--config` | `-c` | `config/model_config.yml` | Path to the YAML config file |
| `--verbose` | `-v` | off | Enable DEBUG-level logging |

### Examples

```bash
# Use default paths
python standalone/main.py

# Custom input / output
python standalone/main.py -i exports/procurement_q1.xlsx -o reports/q1_report.xlsx

# Verbose logging for debugging
python standalone/main.py -v
```

---

## Output file — `output.xlsx`

The report contains six sheets:

| Sheet | Contents | Chart |
|---|---|---|
| `Summary` | KPI tiles: vendor count, total spend, anomaly count, cluster count | Spend by category (bar) |
| `Entity_Resolution` | Raw → canonical vendor name mapping with match scores | — |
| `Vendor_Scores` | Vendor + category scores (0–100) with GREEN / AMBER / RED bands | Top-20 scores (horizontal bar, colour-coded) |
| `Consolidation_Clusters` | Cluster summaries with estimated savings | Savings per cluster (column) |
| `Consolidation_Members` | Vendor membership per cluster | — |
| `Anomaly_Flags` | Flagged purchase orders with z-scores and severity | Severity breakdown (pie) |

---

## Running the tests

```bash
pytest standalone/tests/ -v
```

With coverage:

```bash
pytest standalone/tests/ -v --cov=standalone --cov-report=term-missing
```

---

## Tuning algorithm parameters

All thresholds and weights are controlled by `config/model_config.yml`.
Changes take effect immediately — no code edit required.

Key parameters:

| Section | Parameter | Effect |
|---|---|---|
| `vendor_scoring` | `saving_pct_weight` | Weight of savings rate in composite score |
| `vendor_scoring` | `band_green_min` / `band_amber_min` | Score thresholds for GREEN / AMBER bands |
| `anomaly_detection` | `contamination_factor` | Expected fraction of anomalous POs (0.01–0.50) |
| `entity_resolution` | `match_threshold` | Minimum fuzzy-match score to merge vendor names (0–100) |
| `consolidation` | `n_clusters` | Number of vendor clusters (`auto` or integer) |
