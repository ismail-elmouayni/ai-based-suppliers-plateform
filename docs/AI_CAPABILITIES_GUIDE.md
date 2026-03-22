# AI Capabilities Guide — Supplier Intelligence Platform

**For: Procurement Managers, Category Buyers, Finance Analysts**

---

## What Does This Platform Do?

The Supplier Intelligence Platform automatically analyses your procurement data to answer three
questions that previously required hours of manual work:

1. **Which suppliers are performing well?** — The platform grades each supplier in each
   category on a 0–100 scale, so you can immediately see your top performers and those
   who need attention.

2. **Where can we reduce the number of suppliers?** — The platform finds groups of
   suppliers delivering similar goods or services and estimates how much you could save
   by consolidating to fewer, better-performing vendors.

3. **Which purchase orders look unusual?** — The platform flags orders where the final
   amount paid differs significantly from what was originally agreed, helping your team
   catch potential overruns, pricing errors, or unauthorized changes before they become
   problems.

All analysis runs automatically on your procurement data. No spreadsheets, no manual
calculations.

---

## 1. Vendor Ranking

### What the score means

Every supplier is given a score from **0 to 100** — think of it like a school grade.
A score of 85 means the supplier is performing very well; a score of 25 means there is
significant room for improvement.

### GREEN / AMBER / RED bands

| Band | Score Range | What it means | Recommended action |
|------|------------|---------------|-------------------|
| 🟢 **GREEN** | 70 – 100 | Strong performer | Continue partnership; consider expanding scope |
| 🟡 **AMBER** | 40 – 69 | Average performer | Review contract; set improvement targets |
| 🔴 **RED** | 0 – 39 | Underperformer | Escalate review; consider alternatives |
| ⚪ **INSUFFICIENT DATA** | — | Too few orders to score | Gather more data before evaluating |

A supplier only receives an INSUFFICIENT DATA band if it has fewer than 3 purchase orders
in a category — this prevents unfair judgements based on a single transaction.

### What feeds the score

The composite score blends three signals:

| Signal | Default weight | What it measures |
|--------|---------------|-----------------|
| **Savings performance** | 50% | How much the supplier consistently saves vs. original price |
| **Spend volume** | 30% | How significant this supplier is to your total spend |
| **Category focus** | 20% | How specialised the supplier is in this category vs. spreading across many |

All three signals are compared against all other suppliers before being combined, so
the score always reflects relative performance, not absolute numbers.

### How to adjust scoring priorities

Open the file `ml-engine/config/model_config.yml` in any text editor. You will see:

```yaml
vendor_scoring:
  saving_pct_weight: 0.50    # ← how much savings matter
  spend_weight: 0.30         # ← how much spend volume matters
  specialization_weight: 0.20  # ← how much category focus matters
```

**Examples:**
- If savings are your top priority: increase `saving_pct_weight` to 0.70, reduce the others
- If you want to prioritise high-spend suppliers: increase `spend_weight`
- The three weights do not need to add up to 1.0 — the system normalises them automatically

After saving the file, trigger a new ML run (see section 6) to apply the changes.

---

## 2. Vendor Consolidation

### What a "cluster" means

The platform groups your suppliers by how similar their spending patterns are across
categories. A **cluster** is a group of suppliers who are all delivering similar goods or
services in the same spend area.

For example, if you have four IT Software vendors each receiving annual spend of
€50,000–€150,000, the platform will group them into one cluster and flag it as a
consolidation opportunity.

### Spend at stake and estimated saving potential

- **Spend at stake** — the total annual spend across all vendors in the cluster. This is
  the budget you could potentially renegotiate.
- **Estimated saving potential** — the difference between the best performer's saving rate
  and the average saving rate across the cluster. This is what you could theoretically
  save by consolidating to the top performer.

### Example narrative

> *Cluster 3 contains 4 IT Software vendors. Their combined annual spend is €550,000.
> The best vendor in this group achieves 18% savings; the cluster average is 12%.
> Consolidating to the top performer could save an estimated €33,000 per year.*

### How to start a consolidation initiative

1. Open the **Consolidation Treemap** in the Superset dashboard
2. Identify the largest clusters with the highest estimated saving
3. Click through to see the individual vendors in each cluster
4. Take the cluster to your next category review meeting
5. Negotiate with the top-performing vendor to take on additional scope

---

## 3. Anomaly Detection

### What an anomaly is

An anomaly is a purchase order where **the final amount paid differs significantly from
what was originally agreed**. This could indicate:

- A price increase that was never formally approved
- A quantity change that slipped through without a contract amendment
- A billing error or duplicate charge
- In rare cases, a fraudulent transaction

The platform does not assume fraud — it simply flags orders that look statistically
unusual so your team can investigate.

### HIGH / MEDIUM / LOW severity

| Severity | What it means | Suggested action |
|----------|--------------|-----------------|
| 🔴 **HIGH** | The spend gap is extremely unusual — more than 3 standard deviations from the norm for this supplier and category | Immediate review with procurement and finance team |
| 🟡 **MEDIUM** | The gap is notable — between 2 and 3 standard deviations | Schedule for review in next category meeting |
| 🟢 **LOW** | Flagged by the AI model but within a more typical range | Monitor; no immediate action required |

### How to read the reason text

Every flagged order shows a reason string. For example:

> *"Spend exceeds original by 45.2% (1,234.56 absolute); 3.1σ above TELEPERFORMANCE SE - IT Software mean gap"*

In plain English this means:
- The final amount paid was 45.2% higher than originally agreed
- The absolute overrun was €1,234.56
- Compared to other TELEPERFORMANCE SE IT Software orders, this overrun is 3.1 times
  larger than normal — the "σ" (sigma) symbol means "standard deviations above average"

### What to do when a HIGH anomaly appears

1. Open the **Anomaly Detection** dashboard in Superset
2. Filter to **HIGH** severity
3. Note the PO number and supplier name
4. Pull the original purchase order from your procurement system
5. Compare the original agreed price with the invoiced amount
6. Escalate to the relevant category buyer and finance business partner

### How to tune sensitivity

Open `ml-engine/config/model_config.yml` and adjust `contamination_factor`:

```yaml
anomaly_detection:
  contamination_factor: 0.05   # 5% of orders flagged
```

- **Increase** (e.g. to 0.10): More orders flagged — better for catch-all audits
- **Decrease** (e.g. to 0.02): Only the most extreme outliers flagged — better for focused investigation

After saving, trigger a new ML run (section 6) to apply the change.

---

## 4. How the AI Works (Non-Technical Overview)

### Supplier name standardisation

Your procurement system may record the same supplier under slightly different names:
"TP GROUP INC", "TELEPERFORMANCE GROUP, INC.", "TELEPERFORMANCE SE". The platform
automatically recognises that these are all the same company and groups them under one
**canonical name** before running any analysis. This means you see one score for
Teleperformance, not four separate entries.

### Vendor ranking algorithm

The system calculates a composite grade by combining three signals — savings performance,
spend volume, and category focus — and blends them according to the weights you configure.
Each signal is compared against all other suppliers first (so a "10% saving" means
something different if everyone else achieves 15% vs. 5%), then the weighted blend is
scaled to a 0–100 score.

### Consolidation clustering

The system builds a mathematical fingerprint for each supplier — a picture of how much
they spend across each category. It then groups suppliers whose fingerprints look similar
using a technique called **K-Means clustering**. The platform automatically determines
the right number of groups from your data. No manual input is needed.

### Anomaly detection

The system learns what "normal" looks like for each supplier and category by studying
the historical pattern of spend gaps (difference between agreed price and final invoice).
It then uses a statistical model called **Isolation Forest** to identify individual orders
that don't fit the normal pattern. Because it learns from your specific data, it doesn't
need any pre-defined rules or historical anomaly labels to get started.

---

## 5. Interpreting the Dashboards

### Vendor Ranking dashboard (Superset)

- **Bar chart** — top 20 vendors by composite score; use the category filter to focus
  on a specific category
- **Pie chart** — distribution across GREEN / AMBER / RED; a large RED segment indicates
  a widespread performance issue in your supply base
- **Sortable table** — full list of all scored vendor+category pairs; sort by score,
  filter by band or category

### Anomaly Detection dashboard

- **Anomaly table** — all flagged POs with severity badge and reason string; click any
  row to see the full detail
- **Score histogram** — distribution of anomaly scores; a heavy right tail means many
  borderline cases; sharp peaks near 1.0 indicate clear outliers

### Consolidation Treemap dashboard

- **Treemap** — each box represents a cluster; box size = total spend at stake;
  colour = estimated saving potential; bigger + darker = highest priority
- **Member table** — click a cluster to see which vendors belong to it and their
  individual spend totals

---

## 6. How to Trigger a Fresh Analysis

The ML pipeline analyses your latest procurement data and refreshes all scores,
clusters, and anomaly flags. You can trigger it in two ways:

### Via the API (no terminal required)

1. Open your browser and go to: http://localhost:8080/swagger
2. Find the section **Admin**
3. Click **POST /api/v1/admin/ml/trigger**
4. Click **Try it out**
5. Enter `{"runType": "FULL"}` in the request body
6. Click **Execute**
7. You will receive a `202 Accepted` response with a `run_id`
8. Check progress at **GET /api/v1/admin/ml/status**

The analysis typically completes within 1–3 minutes for 1,734 records.

### Via Superset

Superset dashboards refresh automatically when you open them if new data exists.
To force an immediate refresh, click the **↻ Refresh** icon on any dashboard.

---

## 7. Glossary

| Term | Plain-English meaning |
|------|-----------------------|
| **OPEX** | Operational expenditure — day-to-day running costs (e.g. maintenance contracts, software subscriptions) |
| **CAPEX** | Capital expenditure — one-time investments in assets (e.g. building construction, major equipment) |
| **Saving %** | The percentage by which the final price was reduced versus the original price. Stored as a decimal (0.15 = 15% savings). Displayed in the API as a percentage (× 100). |
| **Canonical vendor name** | The standardised, "correct" name chosen by the system to represent a supplier, even when the source data spells it differently across orders |
| **Contamination factor** | A configuration parameter (0–0.5) controlling how many orders the anomaly model flags. 0.05 means the model expects 5% of orders to be unusual. Higher = more flags; lower = fewer, more extreme flags only. |
| **Composite score** | A single number (0–100) combining three performance signals according to your configured weights |
| **σ (sigma)** | Standard deviation — a measure of how far a value is from the average. "3σ above mean" means the value is three standard deviations higher than typical, which is very unusual. |
| **Cluster** | A group of suppliers with similar spending patterns across categories, identified automatically by the AI |
| **Spend at stake** | The total annual spend across all vendors in a consolidation cluster — the budget that could be renegotiated |
