#!/bin/bash

# Domino App startup script — Vaccine Batch QC Dashboard
# Domino Apps must run on port 8888

echo "Starting Vaccine Batch QC Dashboard..."

streamlit run app.py \
    --server.port=8888 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
