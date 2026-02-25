#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: ./scan.sh <username> [--deep]"
    echo ""
    echo "Options:"
    echo "  --deep    Run all tools including slower scans"
    exit 1
fi

TARGET=$1
DEEP=$2
TIMESTAMP=$(date +%Y-%m-%d_%H-%M)
REPORT_DIR="reports/${TARGET}_${TIMESTAMP}"

echo "=================================================="
echo "   STARTING OSINT SCAN FOR: $TARGET"
echo "=================================================="

# Create report directory
echo "[*] Creating report directory..."
docker exec osint-runner mkdir -p /app/$REPORT_DIR

# PHASE 1: MAIGRET (Username Enumeration - detailed dossier)
echo "[*] Phase 1: Running Maigret (Username Enumeration)..."
docker exec osint-runner maigret "$TARGET" \
    --html --pdf \
    --output /app/$REPORT_DIR/maigret_report.html &
PID_MAIGRET=$!

# PHASE 2: SHERLOCK (Complementary username search)
echo "[*] Phase 2: Running Sherlock (Username Search)..."
docker exec osint-runner sherlock "$TARGET" \
    --output /app/$REPORT_DIR/sherlock_results.txt &
PID_SHERLOCK=$!

# Wait for parallel scans
echo "[*] Waiting for username enumeration to complete..."
wait $PID_MAIGRET $PID_SHERLOCK

# PHASE 3: ONIONSEARCH (Dark Web)
if [ "$DEEP" = "--deep" ]; then
    echo "[*] Phase 3: Running OnionSearch (Dark Web)..."
    docker exec osint-runner onionsearch "$TARGET" \
        --proxy http://tor-proxy:9050 \
        --output /app/$REPORT_DIR/darkweb_hits.txt
fi

echo "=================================================="
echo "   SCAN COMPLETE"
echo "=================================================="
echo ""
echo "Reports saved to: data/$REPORT_DIR"
echo ""
echo "Access dashboards via your Pangolin NEWT tunnels."
