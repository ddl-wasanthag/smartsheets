"""
domino_poc.py

Domino-side script: reads Vaccine Batch QC Monitoring data from Smartsheet
and produces a summary report + QC status breakdown.

Designed to run as a Domino job or inside a Domino workspace (Jupyter/terminal).

Usage:
    export SMARTSHEET_TOKEN=<your_token>
    export SMARTSHEET_SHEET_ID=<sheet_id>   # or rely on .sheet_id written by setup script
    python domino_poc.py
"""

import os
import sys
import smartsheet
import pandas as pd
from datetime import date

# ---------------------------------------------------------------------------
# Resolve credentials and sheet ID
# ---------------------------------------------------------------------------
TOKEN = os.environ.get("SMARTSHEET_TOKEN")
if not TOKEN:
    raise EnvironmentError("Set the SMARTSHEET_TOKEN environment variable.")

SHEET_ID = os.environ.get("SMARTSHEET_SHEET_ID")
if not SHEET_ID:
    id_file = os.path.join(os.path.dirname(__file__), ".sheet_id")
    if os.path.exists(id_file):
        with open(id_file) as f:
            SHEET_ID = f.read().strip()
    else:
        raise EnvironmentError(
            "Set SMARTSHEET_SHEET_ID env var or run setup_smartsheet.py first."
        )

SHEET_ID = int(SHEET_ID)


# ---------------------------------------------------------------------------
# Fetch sheet from Smartsheet API
# ---------------------------------------------------------------------------
def fetch_sheet_as_dataframe(client: smartsheet.Smartsheet, sheet_id: int) -> pd.DataFrame:
    """Pull a Smartsheet sheet and return it as a pandas DataFrame."""
    print(f"Fetching sheet {sheet_id} from Smartsheet ...")
    sheet = client.Sheets.get_sheet(sheet_id)

    col_names = [col.title for col in sheet.columns]

    records = []
    for row in sheet.rows:
        record = {}
        for cell, col_name in zip(row.cells, col_names):
            record[col_name] = cell.value
        records.append(record)

    df = pd.DataFrame(records, columns=col_names)
    print(f"  Fetched {len(df)} rows, {len(df.columns)} columns.\n")
    return df


# ---------------------------------------------------------------------------
# Analytics helpers
# ---------------------------------------------------------------------------
def cast_numeric(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def print_section(title: str) -> None:
    width = 72
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def qc_summary(df: pd.DataFrame) -> None:
    print_section("QC Status Breakdown")
    counts = df["QC Status"].value_counts()
    total = len(df)
    for status, count in counts.items():
        bar = "#" * int(count / total * 40)
        print(f"  {status:<10} {count:>3}  ({count/total*100:5.1f}%)  {bar}")


def failed_batches(df: pd.DataFrame) -> None:
    print_section("Failed Batches — Action Required")
    fails = df[df["QC Status"] == "Fail"][
        ["Batch ID", "Vaccine Type", "Lot Number", "QC Date", "Analyst", "Notes"]
    ]
    if fails.empty:
        print("  No failed batches found.")
    else:
        print(fails.to_string(index=False))


def potency_stats(df: pd.DataFrame) -> None:
    print_section("Potency (%) Statistics by Vaccine Type")
    stats = (
        df.groupby("Vaccine Type")["Potency (%)"]
        .agg(Count="count", Mean="mean", Min="min", Max="max", Std="std")
        .round(2)
    )
    print(stats.to_string())


def expiry_alert(df: pd.DataFrame, days_ahead: int = 90) -> None:
    print_section(f"Batches Expiring Within {days_ahead} Days")
    today = date.today()
    df["Expiry Date"] = pd.to_datetime(df["Expiry Date"], errors="coerce")
    cutoff = pd.Timestamp(today) + pd.Timedelta(days=days_ahead)
    expiring = df[df["Expiry Date"] <= cutoff].sort_values("Expiry Date")[
        ["Batch ID", "Vaccine Type", "Lot Number", "Expiry Date", "QC Status"]
    ]
    if expiring.empty:
        print(f"  No batches expiring within {days_ahead} days.")
    else:
        print(expiring.to_string(index=False))


def out_of_spec(df: pd.DataFrame) -> None:
    """Flag rows where key QC metrics fall outside typical acceptance criteria."""
    print_section("Out-of-Spec QC Metrics")
    issues = df[
        (df["pH Level"] < 6.8) | (df["pH Level"] > 7.4) |
        (df["Potency (%)"] < 90.0) |
        (df["Endotoxin (EU/mL)"] > 0.20)
    ][["Batch ID", "Vaccine Type", "pH Level", "Potency (%)", "Endotoxin (EU/mL)", "QC Status"]]

    if issues.empty:
        print("  All batches within specification thresholds.")
    else:
        print(f"  {len(issues)} batch(es) with out-of-spec readings:\n")
        print(issues.to_string(index=False))


def analyst_workload(df: pd.DataFrame) -> None:
    print_section("Analyst Workload")
    wl = df.groupby("Analyst")["Batch ID"].count().sort_values(ascending=False)
    wl.name = "Batches Reviewed"
    print(wl.to_string())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    client = smartsheet.Smartsheet(TOKEN)
    client.errors_as_exceptions(True)

    df = fetch_sheet_as_dataframe(client, SHEET_ID)

    # Cast numeric columns
    df = cast_numeric(df, ["pH Level", "Potency (%)", "Endotoxin (EU/mL)", "Storage Temp (°C)"])

    print_section(f"Vaccine Batch QC Monitoring Report  —  {date.today()}")
    print(f"  Sheet ID : {SHEET_ID}")
    print(f"  Total Batches: {len(df)}")
    print(f"  Columns  : {', '.join(df.columns.tolist())}")

    qc_summary(df)
    failed_batches(df)
    potency_stats(df)
    expiry_alert(df, days_ahead=90)
    out_of_spec(df)
    analyst_workload(df)

    # Resolve output directory — prefer Domino dataset, fall back to local dir
    project_name = os.environ.get("DOMINO_PROJECT_NAME")
    if project_name:
        output_dir = f"/domino/datasets/local/{project_name}"
        os.makedirs(output_dir, exist_ok=True)
    else:
        output_dir = os.path.dirname(os.path.abspath(__file__))
        print("\n[INFO] DOMINO_PROJECT_NAME not set — writing to local directory.")

    base_path = os.path.join(output_dir, "vaccine_qc_data")

    csv_path = base_path + ".csv"
    df.to_csv(csv_path, index=False)

    parquet_path = base_path + ".parquet"
    df.to_parquet(parquet_path, index=False, engine="pyarrow")

    print(f"\nData exported to:")
    print(f"  CSV     : {csv_path}")
    print(f"  Parquet : {parquet_path}")


if __name__ == "__main__":
    main()
