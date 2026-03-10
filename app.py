"""
app.py — Vaccine Batch QC Monitoring Dashboard

Streamlit app for Domino Data Lab. Reads vaccine QC data from the Domino
dataset written by domino_poc.py and presents an interactive dashboard.

Runs on port 8888 via app.sh.
"""

import os
import pandas as pd
import streamlit as st
from datetime import date

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Vaccine Batch QC Dashboard",
    page_icon="🧬",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
DATASET_DIR = f"/domino/datasets/local/{os.environ.get('DOMINO_PROJECT_NAME', '')}"
PARQUET_PATH = os.path.join(DATASET_DIR, "vaccine_qc_data.parquet")
CSV_PATH = os.path.join(DATASET_DIR, "vaccine_qc_data.csv")


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    if os.path.exists(PARQUET_PATH):
        df = pd.read_parquet(PARQUET_PATH)
        source = PARQUET_PATH
    elif os.path.exists(CSV_PATH):
        df = pd.read_csv(CSV_PATH)
        source = CSV_PATH
    else:
        st.error(
            f"No data file found. Expected:\n- {PARQUET_PATH}\n- {CSV_PATH}\n\n"
            "Run `domino_poc.py` first to generate the dataset."
        )
        st.stop()

    # Coerce types
    for col in ["pH Level", "Potency (%)", "Endotoxin (EU/mL)", "Storage Temp (°C)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Expiry Date"] = pd.to_datetime(df["Expiry Date"], errors="coerce")
    df["QC Date"] = pd.to_datetime(df["QC Date"], errors="coerce")

    return df, source


df, data_source = load_data()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🧬 Vaccine Batch QC Monitoring")
st.caption(f"Data source: `{data_source}`  •  Refreshes every 5 minutes  •  Last loaded: {date.today()}")
st.divider()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")

vaccine_options = sorted(df["Vaccine Type"].dropna().unique())
selected_vaccines = st.sidebar.multiselect(
    "Vaccine Type", vaccine_options, default=vaccine_options
)

status_options = sorted(df["QC Status"].dropna().unique())
selected_statuses = st.sidebar.multiselect(
    "QC Status", status_options, default=status_options
)

analyst_options = sorted(df["Analyst"].dropna().unique())
selected_analysts = st.sidebar.multiselect(
    "Analyst", analyst_options, default=analyst_options
)

# Apply filters
filtered = df[
    df["Vaccine Type"].isin(selected_vaccines) &
    df["QC Status"].isin(selected_statuses) &
    df["Analyst"].isin(selected_analysts)
]

# ---------------------------------------------------------------------------
# KPI metrics row
# ---------------------------------------------------------------------------
total = len(filtered)
passed = (filtered["QC Status"] == "Pass").sum()
failed = (filtered["QC Status"] == "Fail").sum()
pending = (filtered["QC Status"] == "Pending").sum()
pass_rate = (passed / total * 100) if total > 0 else 0

today = pd.Timestamp(date.today())
expiring_soon = filtered[filtered["Expiry Date"] <= today + pd.Timedelta(days=90)]

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Batches", total)
col2.metric("Pass Rate", f"{pass_rate:.1f}%")
col3.metric("Passed", int(passed))
col4.metric("Failed", int(failed), delta=f"-{failed}" if failed else None,
            delta_color="inverse")
col5.metric("Expiring < 90 days", len(expiring_soon),
            delta_color="inverse" if len(expiring_soon) > 0 else "off")

st.divider()

# ---------------------------------------------------------------------------
# Row 1: QC Status breakdown + Potency by vaccine
# ---------------------------------------------------------------------------
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("QC Status Breakdown")
    status_counts = filtered["QC Status"].value_counts().reset_index()
    status_counts.columns = ["QC Status", "Count"]
    st.bar_chart(status_counts.set_index("QC Status"), color="#4C72B0")

with col_right:
    st.subheader("Avg Potency (%) by Vaccine Type")
    potency = (
        filtered.groupby("Vaccine Type")["Potency (%)"]
        .mean()
        .reset_index()
        .rename(columns={"Potency (%)": "Avg Potency (%)"})
    )
    st.bar_chart(potency.set_index("Vaccine Type"), color="#55A868")
    st.caption("Acceptance criterion: ≥ 90%")

st.divider()

# ---------------------------------------------------------------------------
# Row 2: Out-of-spec alerts + Expiry alerts
# ---------------------------------------------------------------------------
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("⚠️ Out-of-Spec Batches")
    oos = filtered[
        (filtered["pH Level"] < 6.8) | (filtered["pH Level"] > 7.4) |
        (filtered["Potency (%)"] < 90.0) |
        (filtered["Endotoxin (EU/mL)"] > 0.20)
    ][["Batch ID", "Vaccine Type", "pH Level", "Potency (%)", "Endotoxin (EU/mL)", "QC Status"]]

    if oos.empty:
        st.success("All batches within specification.")
    else:
        st.warning(f"{len(oos)} batch(es) out of spec")
        st.dataframe(oos, use_container_width=True, hide_index=True)

with col_right:
    st.subheader("📅 Expiring Within 90 Days")
    exp_display = expiring_soon[
        ["Batch ID", "Vaccine Type", "Lot Number", "Expiry Date", "QC Status"]
    ].sort_values("Expiry Date")

    if exp_display.empty:
        st.success("No batches expiring within 90 days.")
    else:
        st.warning(f"{len(exp_display)} batch(es) expiring soon")
        st.dataframe(exp_display, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Row 3: Failed batches + Analyst workload
# ---------------------------------------------------------------------------
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("❌ Failed Batches")
    fails = filtered[filtered["QC Status"] == "Fail"][
        ["Batch ID", "Vaccine Type", "Lot Number", "QC Date", "Analyst", "Notes"]
    ]
    if fails.empty:
        st.success("No failed batches.")
    else:
        st.dataframe(fails, use_container_width=True, hide_index=True)

with col_right:
    st.subheader("Analyst Workload")
    workload = (
        filtered.groupby("Analyst")["Batch ID"]
        .count()
        .reset_index()
        .rename(columns={"Batch ID": "Batches Reviewed"})
        .sort_values("Batches Reviewed", ascending=False)
    )
    st.bar_chart(workload.set_index("Analyst"), color="#C44E52")

st.divider()

# ---------------------------------------------------------------------------
# Full data table
# ---------------------------------------------------------------------------
st.subheader("Full Batch Data")
st.dataframe(
    filtered.sort_values("Batch ID"),
    use_container_width=True,
    hide_index=True,
)

st.caption(f"Showing {len(filtered)} of {len(df)} total batches based on current filters.")
