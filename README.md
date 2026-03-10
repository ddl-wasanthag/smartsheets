# Domino ↔ Smartsheet Integration POC
### Vaccine Batch QC Monitoring

---

## Overview

This proof-of-concept demonstrates a live integration between **Smartsheet** (as a
collaborative data source) and **Domino Data Lab** (as the analytics and ML platform).

A synthetic **Vaccine Batch QC Monitoring** dataset is used to simulate a realistic
pharma/biotech scenario where QC teams manage batch records in Smartsheet and data
scientists / analysts consume that data programmatically in Domino.

```
┌─────────────────────────┐
│       Smartsheet        │  ← QC teams enter / manage batch records
│  Vaccine Batch QC Sheet │
│  (inside Workspace)     │
└────────────┬────────────┘
             │  Smartsheet REST API (via requests)
             ▼
┌─────────────────────────┐
│     Domino Data Lab     │  ← Jobs, Workspaces, Notebooks
│  domino_poc.py          │
│  pandas DataFrame       │
│  QC Report + CSV/Parquet│
└─────────────────────────┘
```

---

## Repository Structure

```
smartsheets/
├── setup_smartsheet.py   # Creates the sheet in a Smartsheet workspace and loads synthetic data
├── domino_poc.py         # Domino-side script: fetches data, runs QC analytics, writes dataset
├── app.py                # Streamlit dashboard — reads from Domino dataset
├── app.sh                # Domino App startup script (runs app.py on port 8888)
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| Python | 3.9+ |
| Smartsheet account | With API access enabled |
| Smartsheet API token | Generate at **Account > Personal Settings > API Access** |
| Smartsheet workspace | Create a workspace in the Smartsheet UI before running setup |
| Domino Data Lab | Workspace or Job environment (for Step 4) |

---

## Setup & Usage

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Find your Smartsheet Workspace ID

List all your workspaces and their IDs with this curl command:

```bash
curl -s -H "Authorization: Bearer $SMARTSHEET_TOKEN" \
  https://api.smartsheet.com/2.0/workspaces | python3 -m json.tool
```

Example response:
```json
{
  "data": [
    {
      "id": 1502514081228676,
      "name": "domino-poc-workspace",
      "accessLevel": "OWNER",
      "permalink": "https://app.smartsheet.com/workspaces/..."
    }
  ]
}
```

Note the `id` value for the workspace you want to use.

### 3. Configure environment variables

Set the following environment variables before running either script:

```bash
export SMARTSHEET_TOKEN=your_api_token_here
export SMARTSHEET_WORKSPACE_ID=1502514081228676
```

> **Domino tip:** Both variables should be set as **User Environment Variables** in Domino
> so they are automatically available in all your Jobs and Workspaces without
> hardcoding credentials into code.
>
> To set them: **Domino → your avatar (top right) → User Settings → Environment Variables**

### 4. Populate Smartsheet with synthetic data

> Run this **once** to create the sheet inside your workspace and load 30 synthetic QC batch records.

```bash
python setup_smartsheet.py
```

**What it does:**
- Creates a new sheet called `Vaccine Batch QC Monitoring - POC` inside the specified workspace
- Generates 30 realistic synthetic batch records across four vaccine types
- Saves the sheet ID to `.sheet_id` (read automatically by `domino_poc.py`)
- Prints the direct Smartsheet URL to the sheet

### 5. Run the Domino analytics script

**Locally:**
```bash
python domino_poc.py
```

**In Domino (as a Job):**
- Set the **file to run** to `domino_poc.py`
- Ensure `SMARTSHEET_TOKEN` and `SMARTSHEET_WORKSPACE_ID` are set as Domino User Environment Variables
- Optionally set `SMARTSHEET_SHEET_ID` to target a specific sheet by ID (overrides `.sheet_id`)

**Output:**
- Printed QC report in the Job log / terminal
- `vaccine_qc_data.csv` and `vaccine_qc_data.parquet` written to the Domino dataset:
  ```
  /domino/datasets/local/$DOMINO_PROJECT_NAME/
  ```
  `$DOMINO_PROJECT_NAME` is set automatically by Domino at runtime. If running locally
  (where this variable is not set), files are written to the script directory instead.

---

## Dataset Schema

30 synthetic rows are generated, one per vaccine batch, with the following fields:

| Column | Type | Description |
|--------|------|-------------|
| Batch ID | Text | Unique identifier — e.g. `BATCH-0001` |
| Vaccine Type | Text | mRNA-1273 (Moderna), BNT162b2 (Pfizer), Ad26.COV2.S (J&J), ChAdOx1 (AZ) |
| Lot Number | Text | Manufacturing lot number |
| Manufacturing Date | Date | Date of manufacture |
| Expiry Date | Date | Calculated expiry (180–365 days post-manufacture) |
| QC Status | Text | `Pass` / `Fail` / `Pending` |
| pH Level | Number | Target range: 6.8–7.4 |
| Potency (%) | Number | Acceptance criterion: ≥ 90% |
| Endotoxin (EU/mL) | Number | Acceptance criterion: ≤ 0.20 EU/mL |
| Sterility Test | Text | `Pass` / `Fail` |
| Visual Inspection | Text | `Clear` / `Particulates Detected` |
| Storage Temp (°C) | Number | Vaccine-specific (e.g. −25 to −15°C for mRNA-1273) |
| Analyst | Text | Name of the reviewing analyst |
| QC Date | Date | Date the QC review was completed |
| Notes | Text | Free-text flags (e.g. "Flagged for re-test") |

---

## Analytics Report

`domino_poc.py` produces the following report sections:

| Section | Description |
|---------|-------------|
| **QC Status Breakdown** | Pass / Fail / Pending counts with percentage and ASCII bar chart |
| **Failed Batches** | Full list of failed batches with analyst name and notes for follow-up |
| **Potency Statistics** | Mean, min, max, std dev of potency grouped by vaccine type |
| **Expiry Alerts** | Batches expiring within the next 90 days |
| **Out-of-Spec Metrics** | Batches violating pH, potency, or endotoxin thresholds |
| **Analyst Workload** | Number of batches reviewed per analyst |

`vaccine_qc_data.csv` and `vaccine_qc_data.parquet` exports are also written for use
in downstream Domino pipelines, notebooks, or model training. The Parquet file is
preferred for large datasets and Spark-based workflows due to its columnar compression.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SMARTSHEET_TOKEN` | Yes | Smartsheet API personal access token |
| `SMARTSHEET_WORKSPACE_ID` | Yes (setup) | Workspace ID where the sheet will be created |
| `SMARTSHEET_SHEET_ID` | No | Override sheet ID (defaults to value in `.sheet_id`) |
| `DOMINO_PROJECT_NAME` | Auto | Set automatically by Domino — used to resolve the dataset output path |

> Both `SMARTSHEET_TOKEN` and `SMARTSHEET_WORKSPACE_ID` should be configured as
> **Domino User Environment Variables** so they persist across sessions and are
> available to all Jobs and Workspaces automatically.

---

## Streamlit Dashboard (Domino App)

`app.py` is a Streamlit dashboard that reads `vaccine_qc_data.parquet` (or `.csv`
as a fallback) from the Domino dataset and presents an interactive QC monitoring UI.

### Dashboard sections

| Section | Description |
|---------|-------------|
| **KPI metrics** | Total batches, pass rate, passed, failed, expiring soon |
| **QC Status Breakdown** | Bar chart of Pass / Fail / Pending counts |
| **Avg Potency by Vaccine** | Bar chart grouped by vaccine type |
| **Out-of-Spec Batches** | Table of batches violating pH, potency, or endotoxin thresholds |
| **Expiring Within 90 Days** | Sorted table of near-expiry batches |
| **Failed Batches** | Full detail table with analyst and notes |
| **Analyst Workload** | Bar chart of batches reviewed per analyst |
| **Full Batch Data** | Filterable full table of all batches |

Sidebar filters let you slice by **Vaccine Type**, **QC Status**, and **Analyst**.

### Deploying as a Domino App

1. Ensure `domino_poc.py` has been run at least once to populate the dataset.
2. In Domino, go to your project → **App** → publish with:
   - **File**: `app.sh`
3. Domino will serve the dashboard on port 8888.

> `DOMINO_PROJECT_NAME` is injected automatically by Domino so the app resolves
> the dataset path without any manual configuration.

---

## Extending the POC

- **Scheduled refresh** — Run `domino_poc.py` as a scheduled Domino Job to pull
  fresh data from Smartsheet on a recurring basis.
- **Write-back** — Use the Smartsheet API to update QC Status cells or add comments
  from Domino analysis results.
- **Visualization** — Add `matplotlib` / `plotly` charts to the Domino notebook for
  potency trends, expiry timelines, or analyst dashboards.
- **Model integration** — Feed `vaccine_qc_data.parquet` into a Domino Model API to
  predict QC failure risk based on batch attributes.
