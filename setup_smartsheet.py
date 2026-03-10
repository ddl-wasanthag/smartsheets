"""
setup_smartsheet.py

Creates a Vaccine Batch QC Monitoring sheet inside a Smartsheet workspace
and populates it with synthetic data. Run this once to set up the POC data source.

Uses the Smartsheet REST API directly via requests (no SDK version issues).

Usage:
    export SMARTSHEET_TOKEN=<your_token>
    export SMARTSHEET_WORKSPACE_ID=1502514081228676
    python setup_smartsheet.py
"""

import os
import random
import requests
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SHEET_NAME = "Vaccine Batch QC Monitoring - POC"

TOKEN = os.environ.get("SMARTSHEET_TOKEN")
WORKSPACE_ID = os.environ.get("SMARTSHEET_WORKSPACE_ID")

if not TOKEN:
    raise EnvironmentError("Set the SMARTSHEET_TOKEN environment variable before running.")
if not WORKSPACE_ID:
    raise EnvironmentError("Set the SMARTSHEET_WORKSPACE_ID environment variable before running.")

BASE_URL = "https://api.smartsheet.com/2.0"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Synthetic data definitions
# ---------------------------------------------------------------------------
VACCINE_TYPES = ["mRNA-1273 (Moderna)", "BNT162b2 (Pfizer)", "Ad26.COV2.S (J&J)", "ChAdOx1 (AZ)"]
ANALYSTS = ["J. Martinez", "P. Chen", "A. Okafor", "S. Patel", "L. Novak"]
QC_STATUSES = ["Pass", "Pass", "Pass", "Pass", "Fail", "Pending"]   # weighted toward Pass
STORAGE_TEMPS = {
    "mRNA-1273 (Moderna)": (-25, -15),
    "BNT162b2 (Pfizer)":   (-90, -60),
    "Ad26.COV2.S (J&J)":   (2, 8),
    "ChAdOx1 (AZ)":        (2, 8),
}

random.seed(42)


def random_date(start_offset_days: int, end_offset_days: int) -> str:
    base = date.today()
    delta = random.randint(start_offset_days, end_offset_days)
    return (base + timedelta(days=delta)).strftime("%Y-%m-%d")


def synthetic_batch(batch_num: int) -> dict:
    vaccine = random.choice(VACCINE_TYPES)
    mfg_date = random_date(-120, -30)
    exp_date = (
        date.fromisoformat(mfg_date) + timedelta(days=random.randint(180, 365))
    ).strftime("%Y-%m-%d")
    status = random.choice(QC_STATUSES)

    return {
        "Batch ID":           f"BATCH-{batch_num:04d}",
        "Vaccine Type":       vaccine,
        "Lot Number":         f"LOT-{random.randint(100000, 999999)}",
        "Manufacturing Date": mfg_date,
        "Expiry Date":        exp_date,
        "QC Status":          status,
        "pH Level":           round(random.uniform(6.8, 7.4), 2),
        "Potency (%)":        round(random.uniform(85.0, 105.0), 1),
        "Endotoxin (EU/mL)":  round(random.uniform(0.01, 0.25), 3),
        "Sterility Test":     "Pass" if status != "Fail" else random.choice(["Pass", "Fail"]),
        "Visual Inspection":  "Clear" if status != "Fail" else random.choice(["Clear", "Particulates Detected"]),
        "Storage Temp (°C)":  round(random.uniform(*STORAGE_TEMPS[vaccine]), 1),
        "Analyst":            random.choice(ANALYSTS),
        "QC Date":            random_date(-30, 0),
        "Notes":              "" if status == "Pass" else "Flagged for re-test",
    }


# ---------------------------------------------------------------------------
# Column definitions — first entry becomes the primary column
# ---------------------------------------------------------------------------
COLUMNS = [
    ("Batch ID",           "TEXT_NUMBER", True),
    ("Vaccine Type",       "TEXT_NUMBER", False),
    ("Lot Number",         "TEXT_NUMBER", False),
    ("Manufacturing Date", "DATE",        False),
    ("Expiry Date",        "DATE",        False),
    ("QC Status",          "TEXT_NUMBER", False),
    ("pH Level",           "TEXT_NUMBER", False),
    ("Potency (%)",        "TEXT_NUMBER", False),
    ("Endotoxin (EU/mL)",  "TEXT_NUMBER", False),
    ("Sterility Test",     "TEXT_NUMBER", False),
    ("Visual Inspection",  "TEXT_NUMBER", False),
    ("Storage Temp (°C)",  "TEXT_NUMBER", False),
    ("Analyst",            "TEXT_NUMBER", False),
    ("QC Date",            "DATE",        False),
    ("Notes",              "TEXT_NUMBER", False),
]

NUM_BATCHES = 30


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def api_post(path: str, payload) -> dict:
    resp = requests.post(f"{BASE_URL}{path}", headers=HEADERS, json=payload)
    if not resp.ok:
        raise RuntimeError(f"POST {path} failed {resp.status_code}: {resp.text}")
    return resp.json()


def api_get(path: str) -> dict:
    resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS)
    if not resp.ok:
        raise RuntimeError(f"GET {path} failed {resp.status_code}: {resp.text}")
    return resp.json()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # --- 1. Create sheet inside the workspace ---
    print(f"Creating sheet '{SHEET_NAME}' in workspace {WORKSPACE_ID} ...")
    sheet_payload = {
        "name": SHEET_NAME,
        "columns": [
            {"title": title, "type": col_type, "primary": primary}
            for title, col_type, primary in COLUMNS
        ],
    }
    result = api_post(f"/workspaces/{WORKSPACE_ID}/sheets", sheet_payload)
    sheet_id = result["result"]["id"]
    print(f"  Sheet created. ID: {sheet_id}")

    # --- 2. Fetch sheet to get column IDs ---
    sheet_data = api_get(f"/sheets/{sheet_id}")
    col_id_map = {col["title"]: col["id"] for col in sheet_data["columns"]}

    # --- 3. Build and add rows ---
    rows = []
    for i in range(1, NUM_BATCHES + 1):
        data = synthetic_batch(i)
        cells = [
            {"columnId": col_id_map[col_name], "value": data[col_name]}
            for col_name, _, _ in COLUMNS
        ]
        rows.append({"toBottom": True, "cells": cells})

    print(f"Adding {NUM_BATCHES} synthetic QC batch rows ...")
    api_post(f"/sheets/{sheet_id}/rows", rows)
    print("  Done.")

    # --- 4. Save sheet ID for domino_poc.py ---
    id_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".sheet_id")
    with open(id_file, "w") as f:
        f.write(str(sheet_id))

    print(f"\nSheet URL: https://app.smartsheet.com/sheets/{sheet_id}")
    print(f"Sheet ID saved to: {id_file}  (read automatically by domino_poc.py)")


if __name__ == "__main__":
    main()
